"""Notion MCP Client — connects to Notion via the official MCP server over stdio."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rich.console import Console

from notion_reverse_autopilot.config import config

console = Console()

# Map of logical operation -> list of known tool names across server versions
# The first match found in discovered tools wins.
TOOL_MAP = {
    "search": [
        "API-post-search", "search", "search-content",
        "notion-search", "notion_search", "post-search",
    ],
    "get_page": [
        "API-retrieve-a-page", "retrieve-a-page",
        "notion-fetch", "notion_retrieve_page",
    ],
    "get_blocks": [
        "API-get-block-children", "get-block-children",
        "retrieve-block-children", "get-page-content",
        "notion_retrieve_block_children",
    ],
    "get_database": [
        "API-retrieve-a-database", "retrieve-a-database",
        "notion_retrieve_database",
    ],
    "create_page": [
        "API-post-page", "create-a-page", "post-page",
        "notion-create-pages", "notion_create_page",
    ],
    "update_page": [
        "API-patch-page", "update-a-page", "patch-page",
        "update-page-properties", "notion-update-page",
        "notion_update_page_properties",
    ],
    "append_blocks": [
        "API-patch-block-children", "patch-block-children",
        "append-block-children", "append-a-block",
        "notion_append_block_children",
    ],
    "create_database": [
        "API-create-a-data-source", "create-a-database",
        "create-a-data-source", "notion-create-database",
        "notion_create_database",
    ],
}


class NotionMCPClient:
    """Communicates with Notion through the official @notionhq/notion-mcp-server via MCP protocol."""

    def __init__(self):
        self._session: ClientSession | None = None
        self._cm_stdio = None
        self._cm_session = None
        self._available_tools: set[str] = set()
        self._resolved: dict[str, str | None] = {}  # operation -> actual tool name
        self._root_page_id: str | None = None

    async def connect(self):
        """Spawn the Notion MCP server and establish a session."""
        env = {
            "OPENAPI_MCP_HEADERS": json.dumps({
                "Authorization": f"Bearer {config.NOTION_API_TOKEN}",
                "Notion-Version": config.NOTION_VERSION,
            }),
            "PATH": os.environ.get("PATH", ""),
        }
        if sys.platform == "win32":
            for key in ("APPDATA", "USERPROFILE", "SYSTEMROOT", "HOMEDRIVE", "HOMEPATH", "TEMP", "TMP"):
                val = os.environ.get(key, "")
                if val:
                    env[key] = val

        if sys.platform == "win32":
            command = "cmd"
            args = ["/c", "npx", "-y", "@notionhq/notion-mcp-server"]
        else:
            command = "npx"
            args = ["-y", "@notionhq/notion-mcp-server"]

        server_params = StdioServerParameters(command=command, args=args, env=env)

        self._cm_stdio = stdio_client(server_params)
        read, write = await self._cm_stdio.__aenter__()

        self._cm_session = ClientSession(read, write)
        self._session = await self._cm_session.__aenter__()

        await self._session.initialize()
        await self._discover_tools()

    async def _discover_tools(self):
        """Discover all available MCP tools and resolve the operation map."""
        resp = await self._session.list_tools()
        self._available_tools = {t.name for t in resp.tools}
        console.print(f"[dim]Discovered {len(self._available_tools)} MCP tools: {', '.join(sorted(self._available_tools))}[/]")

        # Resolve each logical operation to the first matching real tool
        for operation, candidates in TOOL_MAP.items():
            self._resolved[operation] = None
            for candidate in candidates:
                if candidate in self._available_tools:
                    self._resolved[operation] = candidate
                    break

        # Log resolved mappings for debugging
        for op, tool in self._resolved.items():
            status = f"[green]{tool}[/]" if tool else "[red]NOT FOUND[/]"
            console.print(f"[dim]  {op} -> {status}[/]")

    def _tool(self, operation: str) -> str | None:
        """Get the resolved tool name for a logical operation."""
        return self._resolved.get(operation)

    async def close(self):
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
        tool = self._tool("search")
        if not tool:
            console.print("[red]No search tool found[/]")
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
        tool = self._tool("get_page")
        if not tool:
            return {}
        data = await self._call(tool, {"page_id": page_id})
        return data if isinstance(data, dict) else {}

    async def get_page_content(self, page_id: str) -> list[dict]:
        tool = self._tool("get_blocks")
        if not tool:
            return []

        data = await self._call(tool, {"block_id": page_id})
        if data is None:
            data = await self._call(tool, {"page_id": page_id})

        if isinstance(data, dict):
            return data.get("results", data.get("children", []))
        if isinstance(data, list):
            return data
        return []

    async def get_database(self, database_id: str) -> dict:
        tool = self._tool("get_database")
        if not tool:
            return {}
        data = await self._call(tool, {"database_id": database_id})
        return data if isinstance(data, dict) else {}

    # ── WRITE operations ─────────────────────────────────────────

    async def ensure_root_page(self) -> str:
        if self._root_page_id:
            return self._root_page_id

        results = await self.search_all_pages(query="Autopilot Hub")
        for r in results:
            if self.extract_title(r).strip() == "Autopilot Hub":
                self._root_page_id = r["id"]
                return self._root_page_id

        tool = self._tool("create_page")
        if not tool:
            raise RuntimeError(f"No page creation tool found. Available: {sorted(self._available_tools)}")

        # Try workspace-level parent first (appears at top of sidebar)
        page = None
        for parent_format in [
            {"type": "workspace", "workspace": True},
            {"workspace": True},
        ]:
            try:
                result = await self._call(tool, {
                    "parent": parent_format,
                    "properties": {
                        "title": {"title": [{"text": {"content": "Autopilot Hub"}}]}
                    },
                    "children": [
                        _heading_block("Notion Reverse Autopilot"),
                        _paragraph_block("All auto-generated content lives under this page."),
                        _divider_block(),
                    ],
                })
                if isinstance(result, dict) and result.get("id"):
                    page = result
                    break
            except Exception:
                continue

        # Fallback: nest under a top-level page if workspace parent not supported
        if not isinstance(page, dict) or not page.get("id"):
            all_pages = await self.search_all_pages()
            parent_id = None
            for p in all_pages:
                if p.get("object") == "page":
                    parent_id = p["id"]
                    break
            if not parent_id:
                raise RuntimeError("No pages found. Create at least one page in Notion first.")

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
        root_id = await self.ensure_root_page()
        tool = self._tool("create_page")
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
        tool = self._tool("update_page")
        if not tool:
            return {}
        data = await self._call(tool, {"page_id": page_id, "properties": properties})
        return data if isinstance(data, dict) else {}

    async def append_blocks(self, block_id: str, children: list[dict]) -> dict:
        tool = self._tool("append_blocks")
        if not tool:
            console.print("[red]No append_blocks tool found — cannot write to pages[/]")
            return {}
        data = await self._call(tool, {"block_id": block_id, "children": children})
        return data if isinstance(data, dict) else {}

    async def create_database(self, parent: dict, title: list[dict], properties: dict) -> dict:
        tool = self._tool("create_database")
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


# ── Block builders ───────────────────────────────────────────────

def _heading_block(text: str, level: int = 1) -> dict:
    key = f"heading_{level}"
    return {"object": "block", "type": key, key: {"rich_text": [{"type": "text", "text": {"content": text}}]}}

def _paragraph_block(text: str) -> dict:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]}}

def _divider_block() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}
