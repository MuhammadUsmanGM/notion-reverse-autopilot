"""Auto-Organizer — writes AI-generated structure back into Notion via MCP."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from rich.console import Console

from notion_reverse_autopilot.analyzer import AnalysisResult, PageCategory, Connection
from notion_reverse_autopilot.changelog import ChangeLogger
from notion_reverse_autopilot.notion_mcp import NotionMCPClient
from notion_reverse_autopilot.scanner import WorkspaceSnapshot

console = Console()


@dataclass
class OrganizeAction:
    action_type: str
    target_page_id: str
    target_title: str
    description: str
    details: dict = field(default_factory=dict)


class AutoOrganizer:
    def __init__(self, client: NotionMCPClient, changelog: ChangeLogger):
        self.client = client
        self.changelog = changelog
        self._dashboard_id: str | None = None

    async def organize(self, snapshot: WorkspaceSnapshot, analysis: AnalysisResult) -> list[OrganizeAction]:
        actions: list[OrganizeAction] = []

        console.print("[bold cyan]Starting auto-organization...[/]")

        await self._ensure_dashboard()
        actions.extend(await self._annotate_pages(analysis.categories))
        actions.extend(await self._create_topic_clusters(analysis))
        actions.extend(await self._link_related_pages(analysis.connections))
        actions.extend(await self._update_dashboard(snapshot, analysis))

        console.print(f"[bold green]Completed {len(actions)} organization actions.[/]")
        return actions

    async def _ensure_dashboard(self):
        """Create the Autopilot Dashboard page if it doesn't exist."""
        results = await self.client.search_all_pages(query="Autopilot Dashboard")
        for r in results:
            if self.client.extract_title(r).strip() == "Autopilot Dashboard":
                self._dashboard_id = r["id"]
                return

        page = await self.client.create_page(
            properties={
                "title": {"title": [{"text": {"content": "Autopilot Dashboard"}}]}
            },
            children=[
                _heading_block("Notion Reverse Autopilot"),
                _paragraph_block("This page is auto-generated and updated by your AI workspace agent."),
                _divider_block(),
                _heading_block("Workspace Overview", level=2),
                _paragraph_block("Run 'notion-autopilot organize' to populate this dashboard."),
            ],
        )
        self._dashboard_id = page.get("id")
        if self._dashboard_id:
            self.changelog.log("create_dashboard", "Autopilot Dashboard", "Created master dashboard page")

    async def _annotate_pages(self, categories: list[PageCategory]) -> list[OrganizeAction]:
        """Add a callout block to each page with its AI-assigned category and summary."""
        actions = []
        for cat in categories:
            try:
                tags_str = ", ".join(cat.tags[:5]) if cat.tags else ""
                annotation = (
                    f"[Autopilot] Category: {cat.category}/{cat.subcategory}\n"
                    f"Tags: {tags_str}\n"
                    f"Summary: {cat.summary}"
                )
                await self.client.append_blocks(cat.page_id, [
                    _callout_block(annotation)
                ])
                action = OrganizeAction(
                    action_type="annotate",
                    target_page_id=cat.page_id,
                    target_title=cat.title,
                    description=f"Annotated as '{cat.category}/{cat.subcategory}'",
                    details={"category": cat.category, "tags": cat.tags},
                )
                actions.append(action)
                self.changelog.log("annotate", cat.title, f"Category: {cat.category}")
            except Exception:
                pass
        return actions

    async def _create_topic_clusters(self, analysis: AnalysisResult) -> list[OrganizeAction]:
        actions = []
        if not analysis.topic_clusters:
            return actions

        children = [
            _heading_block("Topic Clusters", level=1),
            _paragraph_block(
                f"Auto-discovered {len(analysis.topic_clusters)} topic clusters "
                f"across {sum(len(v) for v in analysis.topic_clusters.values())} pages."
            ),
            _divider_block(),
        ]

        for cluster_name, page_ids in analysis.topic_clusters.items():
            matching = [c for c in analysis.categories if c.page_id in page_ids]
            children.append(_heading_block(f"{cluster_name.title()}", level=2))
            for m in matching[:20]:
                children.append(_bullet_block(f"{m.title} — {m.summary}"))

        try:
            page = await self.client.create_page(
                properties={
                    "title": {"title": [{"text": {"content": "Topic Clusters — Autopilot"}}]}
                },
                children=children[:100],
            )
            page_id = page.get("id", "")
            if page_id:
                actions.append(OrganizeAction(
                    action_type="create_clusters",
                    target_page_id=page_id,
                    target_title="Topic Clusters",
                    description=f"Created topic clusters page with {len(analysis.topic_clusters)} clusters",
                ))
                self.changelog.log("create_clusters", "Topic Clusters", f"{len(analysis.topic_clusters)} clusters")
        except Exception as e:
            console.print(f"[yellow]Could not create clusters page: {e}[/]")

        return actions

    async def _link_related_pages(self, connections: list[Connection]) -> list[OrganizeAction]:
        actions = []
        for conn in connections:
            if conn.strength < 0.5:
                continue
            try:
                label_map = {"related_to": "Connected", "contradicts": "Contradicts", "builds_on": "Builds on", "duplicate_of": "Duplicate of"}
                label = label_map.get(conn.relationship, "Connected")
                await self.client.append_blocks(conn.page_a_id, [
                    _callout_block(f"[Autopilot] {label}: \"{conn.page_b_title}\" — {conn.explanation}")
                ])
                actions.append(OrganizeAction(
                    action_type="link",
                    target_page_id=conn.page_a_id,
                    target_title=conn.page_a_title,
                    description=f"Linked to '{conn.page_b_title}' ({conn.relationship})",
                ))
                self.changelog.log(
                    "link", conn.page_a_title,
                    f"Linked to {conn.page_b_title}: {conn.relationship}",
                )
            except Exception:
                pass
        return actions

    async def _update_dashboard(self, snapshot: WorkspaceSnapshot, analysis: AnalysisResult) -> list[OrganizeAction]:
        if not self._dashboard_id:
            return []

        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        chaos = snapshot.chaos

        children = [
            _divider_block(),
            _heading_block(f"Last Scan: {now}", level=2),
            _paragraph_block(f"Total items: {snapshot.total_items}"),
            _paragraph_block(f"Health Score: {analysis.health_score:.0f}/100"),
            _paragraph_block(f"Chaos Score: {chaos.total_chaos_score:.1f}/100"),
            _heading_block("Chaos Breakdown", level=3),
            _bullet_block(f"Untagged pages: {chaos.untagged_pages}"),
            _bullet_block(f"Orphan pages: {chaos.orphan_pages}"),
            _bullet_block(f"Empty pages: {chaos.empty_pages}"),
            _bullet_block(f"Duplicate titles: {len(chaos.duplicate_titles)}"),
            _heading_block("Top Insights", level=3),
        ]

        insight_labels = {"pattern": "Pattern", "contradiction": "Contradiction", "blind_spot": "Blind Spot", "prediction": "Prediction", "strength": "Strength"}
        for insight in analysis.insights[:5]:
            label = insight_labels.get(insight.insight_type, "Insight")
            children.append(_bullet_block(f"[{label}] {insight.title}: {insight.description}"))

        try:
            await self.client.append_blocks(self._dashboard_id, children)
            self.changelog.log("update_dashboard", "Autopilot Dashboard", f"Updated with scan from {now}")
            return [OrganizeAction(
                action_type="dashboard",
                target_page_id=self._dashboard_id,
                target_title="Autopilot Dashboard",
                description="Updated dashboard with latest scan results",
            )]
        except Exception as e:
            console.print(f"[yellow]Could not update dashboard: {e}[/]")
            return []


# ── Notion block builders ────────────────────────────────────────

def _heading_block(text: str, level: int = 1) -> dict:
    key = f"heading_{level}"
    return {"object": "block", "type": key, key: {"rich_text": [{"type": "text", "text": {"content": text}}]}}


def _paragraph_block(text: str) -> dict:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]}}


def _bullet_block(text: str) -> dict:
    return {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": text}}]}}


def _divider_block() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def _callout_block(text: str) -> dict:
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [{"type": "text", "text": {"content": text}}],
            "icon": {"type": "emoji", "emoji": "🤖"},
        },
    }
