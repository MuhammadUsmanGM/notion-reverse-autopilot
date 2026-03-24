"""CLI Interface — the main entry point for Notion Reverse Autopilot."""

from __future__ import annotations

import asyncio

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

BANNER = """
[bold cyan]╔══════════════════════════════════════════════╗
║   Notion Reverse Autopilot                   ║
║   Your workspace organizes itself.           ║
╚══════════════════════════════════════════════╝[/]
"""


@click.group()
def cli():
    """Notion Reverse Autopilot — AI that watches your chaos and builds order."""
    pass


@cli.command()
def scan():
    """Scan your workspace and show a chaos report."""
    console.print(BANNER)

    from notion_reverse_autopilot.config import config
    errors = config.validate()
    if errors:
        for e in errors:
            console.print(f"[bold red]Error:[/] {e}")
        raise click.Abort()

    asyncio.run(_scan_async())


async def _scan_async():
    from notion_reverse_autopilot.notion_mcp import NotionMCPClient
    from notion_reverse_autopilot.scanner import WorkspaceScanner

    client = NotionMCPClient()
    try:
        console.print("[dim]Connecting to Notion MCP server...[/]")
        await client.connect()
        console.print("[green]Connected.[/]")

        scanner = WorkspaceScanner(client)
        snapshot = await scanner.scan()

        # Display chaos report
        table = Table(title="Workspace Chaos Report", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="bold")

        table.add_row("Total Items", str(snapshot.total_items))
        table.add_row("Pages", str(len(snapshot.pages)))
        table.add_row("Databases", str(len(snapshot.databases)))
        table.add_row("───", "───")
        table.add_row("Chaos Score", f"{snapshot.chaos.total_chaos_score:.1f}/100")
        table.add_row("Organized by Autopilot", str(snapshot.chaos.annotated_pages))
        table.add_row("Untagged Pages", str(snapshot.chaos.untagged_pages))
        table.add_row("Orphan Pages", str(snapshot.chaos.orphan_pages))
        table.add_row("Empty Pages", str(snapshot.chaos.empty_pages))
        table.add_row("Duplicate Titles", str(len(snapshot.chaos.duplicate_titles)))
        table.add_row("Structureless Pages", str(snapshot.chaos.pages_without_structure))
        table.add_row("Very Long Pages", str(snapshot.chaos.very_long_pages))
        table.add_row("Very Short Pages", str(snapshot.chaos.very_short_pages))

        console.print(table)

        score = snapshot.chaos.total_chaos_score
        if score > 60:
            console.print(Panel("[bold red]Your workspace is in CHAOS mode. Run 'organize' to fix it![/]"))
        elif score > 30:
            console.print(Panel("[bold yellow]Your workspace is messy. Auto-organize recommended.[/]"))
        else:
            console.print(Panel("[bold green]Your workspace is fairly organized![/]"))

    finally:
        await client.close()


@cli.command()
def organize():
    """Run full auto-organize cycle: scan -> analyze -> organize -> briefing."""
    console.print(BANNER)

    from notion_reverse_autopilot.config import config
    errors = config.validate()
    if errors:
        for e in errors:
            console.print(f"[bold red]Error:[/] {e}")
        raise click.Abort()

    from notion_reverse_autopilot.scheduler import run_cycle
    asyncio.run(run_cycle())


@cli.command()
def briefing():
    """Generate a Brain Briefing without reorganizing."""
    console.print(BANNER)

    from notion_reverse_autopilot.config import config
    errors = config.validate()
    if errors:
        for e in errors:
            console.print(f"[bold red]Error:[/] {e}")
        raise click.Abort()

    asyncio.run(_briefing_async())


async def _briefing_async():
    from notion_reverse_autopilot.notion_mcp import NotionMCPClient
    from notion_reverse_autopilot.scanner import WorkspaceScanner
    from notion_reverse_autopilot.analyzer import AIAnalyzer
    from notion_reverse_autopilot.insights import InsightReportGenerator

    client = NotionMCPClient()
    try:
        console.print("[dim]Connecting to Notion MCP server...[/]")
        await client.connect()
        console.print("[green]Connected.[/]")

        scanner = WorkspaceScanner(client)
        snapshot = await scanner.scan()

        analyzer = AIAnalyzer()
        analysis = analyzer.analyze(snapshot)

        reporter = InsightReportGenerator(client)
        await reporter.generate_briefing(snapshot, analysis)
    finally:
        await client.close()


@cli.command("schedule")
@click.option("--interval", default=6, help="Hours between each cycle.")
def schedule_cmd(interval: int):
    """Run autopilot on a recurring schedule."""
    console.print(BANNER)

    from notion_reverse_autopilot.config import config
    errors = config.validate()
    if errors:
        for e in errors:
            console.print(f"[bold red]Error:[/] {e}")
        raise click.Abort()

    from notion_reverse_autopilot.scheduler import start_scheduler
    start_scheduler(interval)


@cli.command()
@click.option("--limit", default=20, help="Number of recent entries to show.")
def history(limit: int):
    """View past changelog entries."""
    console.print(BANNER)

    from notion_reverse_autopilot.changelog import ChangeLogger
    logger = ChangeLogger()
    entries = logger.get_recent(limit)

    if not entries:
        console.print("[dim]No changelog entries found.[/]")
        return

    table = Table(title="Autopilot Changelog", show_header=True)
    table.add_column("Time", style="dim")
    table.add_column("Action", style="cyan")
    table.add_column("Target", style="bold")
    table.add_column("Description")

    for entry in reversed(entries):
        table.add_row(
            entry.get("timestamp", "")[:19],
            entry.get("action", ""),
            entry.get("target", "")[:30],
            entry.get("description", ""),
        )

    console.print(table)


if __name__ == "__main__":
    cli()
