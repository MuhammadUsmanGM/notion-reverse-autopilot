"""AI Analysis Engine — uses any LLM to categorize, find patterns, and generate insights."""

from __future__ import annotations

from dataclasses import dataclass, field

from notion_reverse_autopilot.llm import LLMClient
from notion_reverse_autopilot.scanner import WorkspaceSnapshot, PageSnapshot


@dataclass
class PageCategory:
    page_id: str
    title: str
    category: str
    subcategory: str
    tags: list[str]
    summary: str


@dataclass
class Connection:
    page_a_id: str
    page_a_title: str
    page_b_id: str
    page_b_title: str
    relationship: str
    explanation: str
    strength: float


@dataclass
class CognitiveInsight:
    insight_type: str
    title: str
    description: str
    evidence: list[str]
    confidence: float


@dataclass
class AnalysisResult:
    categories: list[PageCategory] = field(default_factory=list)
    connections: list[Connection] = field(default_factory=list)
    topic_clusters: dict[str, list[str]] = field(default_factory=dict)
    insights: list[CognitiveInsight] = field(default_factory=list)
    workspace_summary: str = ""
    health_score: float = 0.0


class AIAnalyzer:
    def __init__(self):
        self.llm = LLMClient()

    def analyze(self, snapshot: WorkspaceSnapshot) -> AnalysisResult:
        from rich.console import Console
        console = Console()

        result = AnalysisResult()

        all_pages = snapshot.pages + snapshot.databases
        if not all_pages:
            result.workspace_summary = "Empty workspace — nothing to analyze."
            return result

        page_summaries = self._build_page_summaries(all_pages)

        console.print("[dim]AI: Categorizing pages...[/]")
        try:
            result.categories = self._categorize_pages(page_summaries)
        except Exception as e:
            console.print(f"[yellow]Categorization failed, continuing: {e}[/]")

        console.print("[dim]AI: Finding connections...[/]")
        try:
            result.connections = self._find_connections(page_summaries)
        except Exception as e:
            console.print(f"[yellow]Connection finding failed, continuing: {e}[/]")

        result.topic_clusters = self._cluster_topics(result.categories)

        console.print("[dim]AI: Generating insights...[/]")
        try:
            result.insights = self._generate_insights(page_summaries, result)
        except Exception as e:
            console.print(f"[yellow]Insight generation failed, continuing: {e}[/]")

        console.print("[dim]AI: Writing summary...[/]")
        try:
            result.workspace_summary = self._generate_summary(page_summaries, result)
        except Exception as e:
            console.print(f"[yellow]Summary generation failed, continuing: {e}[/]")

        result.health_score = max(0, 100 - snapshot.chaos.total_chaos_score)

        return result

    def _build_page_summaries(self, pages: list[PageSnapshot]) -> str:
        lines = []
        for p in pages[:100]:
            content_preview = p.content_text[:500] if p.content_text else "(empty)"
            lines.append(
                f"[ID: {p.id}] Title: {p.title}\n"
                f"  Type: {p.object_type} | Words: {p.word_count} | "
                f"Tags: {p.has_tags} | Orphan: {p.is_orphan}\n"
                f"  Content: {content_preview}\n"
            )
        return "\n---\n".join(lines)

    def _categorize_pages(self, page_summaries: str) -> list[PageCategory]:
        data = self.llm.ask_json(
            f"""Analyze these Notion pages and categorize each one.

For each page, provide:
- category: one of [project, idea, note, task, journal, reference, meeting, brainstorm, resource, archive, template, personal, work, finance, health, learning]
- subcategory: more specific label
- tags: 2-5 relevant tags
- summary: one-sentence summary

Pages:
{page_summaries}

Respond in JSON format:
{{"pages": [{{"page_id": "...", "title": "...", "category": "...", "subcategory": "...", "tags": ["..."], "summary": "..."}}]}}

Return ONLY valid JSON, no other text."""
        )

        return [
            PageCategory(
                page_id=p["page_id"],
                title=p["title"],
                category=p["category"],
                subcategory=p.get("subcategory", ""),
                tags=p.get("tags", []),
                summary=p.get("summary", ""),
            )
            for p in data.get("pages", [])
        ]

    def _find_connections(self, page_summaries: str) -> list[Connection]:
        data = self.llm.ask_json(
            f"""Analyze these Notion pages and find hidden connections between them.

Look for:
- Pages about related topics that aren't linked
- Ideas that build on each other
- Contradictory commitments or statements
- Duplicate or overlapping content

Pages:
{page_summaries}

Respond in JSON:
{{"connections": [{{"page_a_id": "...", "page_a_title": "...", "page_b_id": "...", "page_b_title": "...", "relationship": "related_to|contradicts|builds_on|duplicate_of", "explanation": "...", "strength": 0.0-1.0}}]}}

Return ONLY valid JSON."""
        )

        return [
            Connection(
                page_a_id=c["page_a_id"],
                page_a_title=c["page_a_title"],
                page_b_id=c["page_b_id"],
                page_b_title=c["page_b_title"],
                relationship=c["relationship"],
                explanation=c["explanation"],
                strength=c.get("strength", 0.5),
            )
            for c in data.get("connections", [])
        ]

    def _cluster_topics(self, categories: list[PageCategory]) -> dict[str, list[str]]:
        clusters: dict[str, list[str]] = {}
        for cat in categories:
            key = cat.category
            if key not in clusters:
                clusters[key] = []
            clusters[key].append(cat.page_id)
        return clusters

    def _generate_insights(self, page_summaries: str, partial_result: AnalysisResult) -> list[CognitiveInsight]:
        connections_text = "\n".join(
            f"- {c.page_a_title} <-> {c.page_b_title}: {c.relationship} ({c.explanation})"
            for c in partial_result.connections[:20]
        )
        categories_text = "\n".join(
            f"- {c.title}: {c.category}/{c.subcategory} — {c.summary}"
            for c in partial_result.categories[:30]
        )

        data = self.llm.ask_json(
            f"""You are a cognitive analyst. Analyze this person's Notion workspace to discover deep insights about HOW THEY THINK and WORK.

Page summaries:
{page_summaries[:3000]}

Categories:
{categories_text}

Connections found:
{connections_text}

Generate insights in these categories:
1. "pattern" — recurring behavioral/thinking patterns
2. "contradiction" — conflicting commitments, goals, or beliefs
3. "blind_spot" — areas they're neglecting or avoiding
4. "prediction" — what they'll likely need or do next based on patterns
5. "strength" — cognitive strengths evident from their workspace

Respond in JSON:
{{"insights": [{{"insight_type": "...", "title": "...", "description": "...", "evidence": ["page title 1", "page title 2"], "confidence": 0.0-1.0}}]}}

Be specific, surprising, and genuinely useful. Avoid generic observations.
Return ONLY valid JSON."""
        )

        return [
            CognitiveInsight(
                insight_type=i["insight_type"],
                title=i["title"],
                description=i["description"],
                evidence=i.get("evidence", []),
                confidence=i.get("confidence", 0.5),
            )
            for i in data.get("insights", [])
        ]

    def _generate_summary(self, page_summaries: str, result: AnalysisResult) -> str:
        num_cats = len(set(c.category for c in result.categories))
        num_connections = len(result.connections)
        num_insights = len(result.insights)

        return self.llm.ask(
            f"""Write a 3-4 sentence summary of this Notion workspace.
Found {len(result.categories)} pages across {num_cats} categories.
Found {num_connections} hidden connections and {num_insights} cognitive insights.
Health score: {result.health_score}/100.

Key insights: {'; '.join(i.title for i in result.insights[:5])}

Write it as a personal workspace profile — direct, insightful, no fluff.""",
            max_tokens=1024,
        )
