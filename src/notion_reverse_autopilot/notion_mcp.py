"""Notion MCP Client — connects to Notion via the official MCP server over stdio."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rich.console import Console

from notion_reverse_autopilot.config import config

console = Console()


class NotionMCPClient:
    """Communicates with Notion through the official @notionhq/notion-mcp-server via MCP protocol."""

    def __init__(self):
        self._session: ClientSession | None = None
        self._cm_stdio = None
        self._cm_session = None
        self._tools: dict[str, dict] = {}  # name -> {description, inputSchema}
        self._root_page_id: str | None = None  # parent page for created content

    async def connect(self):
        """Spawn the Notion MCP server and establish a session."""
        env = {
            "OPENAPI_MCP_HEADERS": json.dumps({
                "Authorization": f"Bearer {config.NOTION_API_TOKEN}",
                "Notion-Version": config.NOTION_VERSION,
            }),
            "PATH": os.environ.get("PATH", ""),
        }
        # Windows needs extra env vars for npx/node to work
        if sys.platform == "win32":
            for key in ("APPDATA", "USERPROFILE", "SYSTEMROOT", "HOMEDRIVE", "HOMEPATH", "TEMP", "TMP"):
                val = os.environ.get(key, "")
                if val:
                    env[key] = val

        # On Windows, npx is a .cmd script — must invoke via cmd.exe
        if sys.platform == "win32":
            command = "cmd"
            args = ["/c", "npx", "-y", "@notionhq/notion-mcp-server"]
        else:
            command = "npx"
            args = ["-y", "@notionhq/notion-mcp-server"]

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=env,
        )

        self._cm_stdio = stdio_client(server_params)
        read, write = await self._cm_stdio.__aenter__()

        self._cm_session = ClientSession(read, write)
        self._session = await self._cm_session.__aenter__()

        await self._session.initialize()

        # Auto-discover available tools so we use the correct names
        await self._discover_tools()

    async def _discover_tools(self):
        """Discover all available MCP tool names and cache them."""
        resp = await self._session.list_tools()
        for tool in resp.tools:
            self._tools[tool.name] = {
                "description": tool.description,
                "inputSchema": tool.inputSchema,
            }
        console.print(f"[dim]Discovered {len(self._tools)} MCP tools: {', '.join(sorted(self._tools.keys()))}[/]")

    def _find_tool(self, *candidates: str) -> str | None:
        """Find the first matching tool name from a list of candidates."""
        for name in candidates:
            if name in self._tools:
                return name
        # Fuzzy fallback: check if any tool name contains any candidate keyword
        for name in candidates:
            keyword = name.replace("-", "").replace("_", "").lower()
            for tool_name in self._tools:
                if keyword in tool_name.replace("-", "").replace("_", "").lower():
                    return tool_name
        return None

    async def close(self):
        """Shut down the MCP session and server process."""
        if self._cm_session:
            await self._cm_session.__aexit__(None, None, None)
        if self._cm_stdio:
            await self._cm_stdio.__aexit__(None, None, None)
        self._session = None

    async def _call(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Call an MCP tool and return the parsed result."""
        result = await self._session.call_tool(tool_name, arguments=arguments)
        if result.content:
            for block in result.content:
                if hasattr(block, "text"):
                    try:
                        return json.loads(block.text)
                    except json.JSONDecodeError:
                        return block.text
        return None

    # ── READ operations ──────────────────────────────────────────

    async def search_all_pages(self, query: str = "") -> list[dict]:
        """Search across the entire workspace."""
        tool = self._find_tool("search", "search-content", "notion-search", "notion_search")
        if not tool:
            console.print("[red]No search tool found in MCP server[/]")
            return []

        args = {}
        if query:
            args["query"] = query

        data = await self._call(tool, args)
        if isinstance(data, dict):
            return data.get("results", [])
        if isinstance(data, list):
            return data
        return []

    async def get_page(self, page_id: str) -> dict:
        tool = self._find_tool("retrieve-a-page", "notion-fetch", "notion_retrieve_page")
        if not tool:
            return {}
        data = await self._call(tool, {"page_id": page_id})
        return data if isinstance(data, dict) else {}

    async def get_page_content(self, page_id: str) -> list[dict]:
        """Get block children of a page."""
        tool = self._find_tool(
            "get-page-content", "retrieve-block-children",
            "get-block-children", "notion_retrieve_block_children",
        )
        if not tool:
            return []

        # Try both parameter name conventions
        data = await self._call(tool, {"block_id": page_id})
        if data is None:
            data = await self._call(tool, {"page_id": page_id})

        if isinstance(data, dict):
            return data.get("results", data.get("children", []))
        if isinstance(data, list):
            return data
        return []

    async def get_database(self, database_id: str) -> dict:
        tool = self._find_tool("retrieve-a-database", "notion_retrieve_database")
        if not tool:
            return {}
        data = await self._call(tool, {"database_id": database_id})
        return data if isinstance(data, dict) else {}

    # ── WRITE operations ─────────────────────────────────────────

    async def ensure_root_page(self) -> str:
        """Find or create a root 'Autopilot Hub' page to nest all created content under."""
        if self._root_page_id:
            return self._root_page_id

        # Search for existing hub page
        results = await self.search_all_pages(query="Autopilot Hub")
        for r in results:
            if self.extract_title(r).strip() == "Autopilot Hub":
                self._root_page_id = r["id"]
                return self._root_page_id

        # Create root page — we need an existing page as parent
        # First, find ANY page in the workspace to use as parent
        all_pages = await self.search_all_pages()
        parent_id = None
        for p in all_pages:
            if p.get("object") == "page":
                parent_id = p["id"]
                break

        if not parent_id:
            raise RuntimeError("No pages found in workspace. Please create at least one page in Notion first.")

        tool = self._find_tool("create-a-page", "notion-create-pages", "notion_create_page")
        if not tool:
            raise RuntimeError("No page creation tool found in MCP server")

        page = await self._call(tool, {
            "parent": {"type": "page_id", "page_id": parent_id},
            "properties": {
                "title": {"title": [{"text": {"content": "Autopilot Hub"}}]}
            },
            "children": [
                _heading_block("Notion Reverse Autopilot"),
                _paragraph_block("All auto-generated content lives under this page."),
                _divider_block(),
            ],
        })

        if isinstance(page, dict) and page.get("id"):
            self._root_page_id = page["id"]
            return self._root_page_id
        raise RuntimeError("Failed to create Autopilot Hub page")

    async def create_page(self, properties: dict, children: list[dict] | None = None) -> dict:
        """Create a page under the Autopilot Hub."""
        root_id = await self.ensure_root_page()

        tool = self._find_tool("create-a-page", "notion-create-pages", "notion_create_page")
        if not tool:
            return {}

        args: dict[str, Any] = {
            "parent": {"type": "page_id", "page_id": root_id},
            "properties": properties,
        }
        if children:
            args["children"] = children

        data = await self._call(tool, args)
        return data if isinstance(data, dict) else {}

    async def update_page(self, page_id: str, properties: dict) -> dict:
        tool = self._find_tool(
            "update-page-properties", "update-a-page",
            "notion-update-page", "notion_update_page_properties",
        )
        if not tool:
            return {}
        data = await self._call(tool, {"page_id": page_id, "properties": properties})
        return data if isinstance(data, dict) else {}

    async def append_blocks(self, block_id: str, children: list[dict]) -> dict:
        tool = self._find_tool(
            "append-block-children", "append-a-block",
            "notion_append_block_children",
        )
        if not tool:
            return {}
        data = await self._call(tool, {"block_id": block_id, "children": children})
        return data if isinstance(data, dict) else {}

    async def create_database(self, parent: dict, title: list[dict], properties: dict) -> dict:
        tool = self._find_tool(
            "create-a-database", "create-a-data-source",
            "notion-create-database", "notion_create_database",
        )
        if not tool:
            return {}
        data = await self._call(tool, {
            "parent": parent,
            "title": title,
            "properties": properties,
        })
        return data if isinstance(data, dict) else {}

    # ── HELPERS ───────────────────────────────────────────────────

    def extract_title(self, page_or_db: dict) -> str:
        props = page_or_db.get("properties", {})
        for prop in props.values():
            if prop.get("type") == "title":
                title_parts = prop.get("title", [])
                return "".join(t.get("plain_text", "") for t in title_parts)
        title_list = page_or_db.get("title", [])
        if isinstance(title_list, list):
            return "".join(t.get("plain_text", "") for t in title_list)
        return "Untitled"

    def blocks_to_text(self, blocks: list[dict]) -> str:
        """Convert block tree to plain text for AI analysis."""
        lines = []
        for block in blocks:
            btype = block.get("type", "")
            bdata = block.get(btype, {})
            if isinstance(bdata, dict):
                rich_texts = bdata.get("rich_text", [])
                text = "".join(rt.get("plain_text", "") for rt in rich_texts)
                if text:
                    lines.append(text)
        return "\n".join(lines)


# ── Block builders (used by ensure_root_page) ────────────────────

def _heading_block(text: str, level: int = 1) -> dict:
    key = f"heading_{level}"
    return {"object": "block", "type": key, key: {"rich_text": [{"type": "text", "text": {"content": text}}]}}

def _paragraph_block(text: str) -> dict:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]}}

def _divider_block() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}
