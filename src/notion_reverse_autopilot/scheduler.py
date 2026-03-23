"""Scheduler — runs the autopilot pipeline on a recurring interval."""

from __future__ import annotations

import asyncio
import time

import schedule
from rich.console import Console

console = Console()


async def run_cycle():
    """Execute one full scan -> analyze -> organize -> briefing cycle."""
    from notion_reverse_autopilot.notion_mcp import NotionMCPClient
    from notion_reverse_autopilot.scanner import WorkspaceScanner
    from notion_reverse_autopilot.analyzer import AIAnalyzer
    from notion_reverse_autopilot.changelog import ChangeLogger
    from notion_reverse_autopilot.organizer import AutoOrganizer
    from notion_reverse_autopilot.insights import InsightReportGenerator

    console.print("\n[bold cyan]═══ Autopilot Cycle Starting ═══[/]")

    client = NotionMCPClient()

    try:
        console.print("[dim]Connecting to Notion MCP server...[/]")
        await client.connect()
        console.print("[green]Connected to Notion MCP server.[/]")

        changelog = ChangeLogger()

        scanner = WorkspaceScanner(client)
        snapshot = await scanner.scan()

        analyzer = AIAnalyzer()
        analysis = analyzer.analyze(snapshot)

        organizer = AutoOrganizer(client, changelog)
        await organizer.organize(snapshot, analysis)

        reporter = InsightReportGenerator(client)
        await reporter.generate_briefing(snapshot, analysis)

        console.print("[bold green]═══ Cycle Complete ═══[/]\n")
    finally:
        await client.close()


def start_scheduler(interval_hours: int):
    """Start the recurring scheduler."""
    console.print(f"[bold cyan]Scheduling autopilot every {interval_hours} hour(s).[/]")
    console.print("[dim]Press Ctrl+C to stop.[/]\n")

    # Run immediately on start
    asyncio.run(run_cycle())

    def _run():
        asyncio.run(run_cycle())

    schedule.every(interval_hours).hours.do(_run)

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Scheduler stopped.[/]")
