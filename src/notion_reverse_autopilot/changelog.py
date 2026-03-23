"""Change Log — tracks every auto-organization action for transparency and undo."""

from __future__ import annotations

import datetime
import json

from notion_reverse_autopilot.config import config


class ChangeLogger:
    def __init__(self):
        self.log_file = config.DATA_DIR / "changelog.jsonl"
        self._entries: list[dict] = []

    def log(self, action_type: str, target: str, description: str, details: dict | None = None):
        entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "action": action_type,
            "target": target,
            "description": description,
            "details": details or {},
        }
        self._entries.append(entry)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def get_recent(self, limit: int = 50) -> list[dict]:
        if not self.log_file.exists():
            return []
        lines = self.log_file.read_text(encoding="utf-8").strip().split("\n")
        entries = []
        for line in lines[-limit:]:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries

    def get_session_entries(self) -> list[dict]:
        return list(self._entries)
