# Notion Reverse Autopilot

**Your workspace organizes itself.**

Most productivity tools assume you're organized. This one assumes you're NOT — and fixes it autonomously.

Notion Reverse Autopilot is an AI agent that continuously watches your messy Notion workspace, auto-organizes everything, discovers hidden patterns about how you think, and surfaces insights you never knew existed.

> *"What if you never had to organize Notion again — and it actually understood you better than you understand yourself?"*

---

## How It Works

```
You dump chaos into Notion
        |
        v
┌─────────────────────────┐
│   Workspace Scanner     │  Crawls every page, database, block
└────────┬────────────────┘
         v
┌─────────────────────────┐
│   AI Analysis Engine    │  Categorizes, finds connections,
│                         │  detects cognitive patterns
└────────┬────────────────┘
         v
┌─────────────────────────┐
│   Auto-Organizer        │  Tags pages, links related ideas,
│                         │  builds topic clusters & dashboards
└────────┬────────────────┘
         v
┌─────────────────────────┐
│   Brain Briefing        │  Health score, hidden connections,
│                         │  contradictions, predictions
└─────────────────────────┘
```

**You stay messy. The AI builds order.**

---

## Features

- **Chaos Detection** — Scans your workspace and scores how messy it is (untagged pages, orphans, duplicates, empty pages)
- **Auto-Categorization** — AI classifies every page (project, idea, task, journal, reference, etc.)
- **Hidden Connection Discovery** — Finds links between pages you never connected yourself
- **Topic Clustering** — Groups related content into auto-generated clusters
- **Cognitive Insights** — Analyzes your thinking patterns, blind spots, contradictions, and strengths
- **Brain Briefing** — Rich Notion page with your workspace health, insights, and predictions
- **Autopilot Dashboard** — Master overview page updated on every scan
- **Full Changelog** — Every action logged for transparency and undo
- **Scheduled Mode** — Runs automatically every X hours in the background
- **Multi-Provider AI** — Works with Groq (free), Gemini (free), Ollama (free/local), or Anthropic

---

## Quick Start

### 1. Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- A [Notion Integration Token](https://www.notion.so/my-integrations) (free)
- An AI provider API key (Groq is free — get one at [console.groq.com](https://console.groq.com))

### 2. Install

```bash
git clone https://github.com/MuhammadUsmanGM/notion-reverse-autopilot.git
cd notion-reverse-autopilot
uv sync
```

### 3. Configure

```bash
cp .env.example .env
```

Edit `.env` with your keys:

```env
AI_PROVIDER=groq
GROQ_API_KEY=your-key-here
NOTION_API_TOKEN=your-notion-token-here
```

### 4. Connect Notion

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Create a new integration
3. Copy the token into your `.env`
4. Share your Notion pages/databases with the integration (click "..." on a page > "Connect to" > your integration)

### 5. Run

```bash
# See how messy your workspace is
uv run notion-autopilot scan

# Full auto-organize + brain briefing
uv run notion-autopilot organize

# Generate brain briefing only (no changes)
uv run notion-autopilot briefing

# Run on autopilot every 6 hours
uv run notion-autopilot schedule --interval 6

# View change history
uv run notion-autopilot history
```

---

## AI Providers

Pick whichever fits your budget. All produce great results.

| Provider | Cost | Speed | Setup |
|---|---|---|---|
| **Groq** | Free | Very fast | [console.groq.com](https://console.groq.com) |
| **Gemini** | Free tier | Fast | [aistudio.google.com](https://aistudio.google.com) |
| **Ollama** | Free (local) | Depends on HW | [ollama.com](https://ollama.com) |
| **Anthropic** | Paid | Fast | [console.anthropic.com](https://console.anthropic.com) |

Set `AI_PROVIDER` in your `.env` to switch. Default is `groq`.

---

## What Gets Created in Your Workspace

| Page | Description |
|---|---|
| **Autopilot Dashboard** | Master overview with health score, chaos breakdown, top insights |
| **Brain Briefing** | Timestamped report with cognitive profile, hidden connections, predictions |
| **Topic Clusters** | Auto-grouped pages by theme |
| **Callout blocks** | Added to pages showing discovered connections |

Every action is logged locally at `~/.notion-autopilot/changelog.jsonl`.

---

## Brain Briefing Contents

Each briefing includes:

- **Workspace Health Score** — 0-100 scale of how organized vs chaotic
- **Cognitive Profile** — How you think and work based on your content
- **Recurring Patterns** — Behavioral patterns across your workspace
- **Hidden Connections** — "Your note X relates to project Y"
- **Contradictions** — Conflicting commitments or ideas you didn't notice
- **Blind Spots** — Areas you're neglecting
- **Predictions** — What you'll likely need next based on your patterns
- **Topic Clusters** — All discovered groupings

---

## Project Structure

```
notion-reverse-autopilot/
├── src/
│   └── notion_reverse_autopilot/
│       ├── __init__.py
│       ├── __main__.py      # python -m entry point
│       ├── cli.py           # CLI commands (scan, organize, briefing, schedule, history)
│       ├── config.py        # Configuration & env management
│       ├── llm.py           # Multi-provider AI interface (Groq/Gemini/Ollama/Anthropic)
│       ├── notion_mcp.py    # Notion API client (read/write pages, databases, blocks)
│       ├── scanner.py       # Workspace crawler & chaos detector
│       ├── analyzer.py      # AI categorization, connections, cognitive insights
│       ├── organizer.py     # Auto-tagger, linker, dashboard builder
│       ├── insights.py      # Brain Briefing page generator
│       ├── scheduler.py     # Recurring cron-like scheduler
│       └── changelog.py     # Action logger for transparency
├── .env.example
├── pyproject.toml
├── uv.lock
└── README.md
```

---

## Built With

- **Notion API** — Workspace read/write via REST API (MCP-compatible)
- **Claude / Llama 3 / Gemini** — AI analysis engine (your choice)
- **Python** — Core runtime
- **uv** — Package management
- **Click** — CLI framework
- **Rich** — Terminal UI
- **httpx** — HTTP client

---

## License

MIT

---

Built for the [Notion MCP Challenge](https://dev.to/challenges/notion) on DEV.
