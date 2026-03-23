import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    # AI Provider: "groq" (free), "gemini" (free), "ollama" (free/local), "anthropic" (paid)
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "groq")

    # Provider API keys (only need the one you're using)
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # Model per provider
    MODELS: dict = {
        "groq": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "gemini": os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"),
        "ollama": os.getenv("OLLAMA_MODEL", "llama3"),
        "anthropic": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
    }

    # Notion
    NOTION_API_TOKEN: str = os.getenv("NOTION_API_TOKEN", "")
    NOTION_API_BASE: str = "https://api.notion.com/v1"
    NOTION_VERSION: str = "2022-06-28"

    # General
    SCAN_INTERVAL_HOURS: int = int(os.getenv("SCAN_INTERVAL_HOURS", "6"))
    MAX_PAGES_PER_SCAN: int = 500
    DATA_DIR: Path = Path.home() / ".notion-autopilot"

    def __init__(self):
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def ai_model(self) -> str:
        return self.MODELS.get(self.AI_PROVIDER, self.MODELS["groq"])

    def validate(self) -> list[str]:
        errors = []
        if not self.NOTION_API_TOKEN:
            errors.append("NOTION_API_TOKEN is not set")

        provider = self.AI_PROVIDER
        if provider == "anthropic" and not self.ANTHROPIC_API_KEY:
            errors.append("ANTHROPIC_API_KEY is not set (required for anthropic provider)")
        elif provider == "groq" and not self.GROQ_API_KEY:
            errors.append("GROQ_API_KEY is not set (get free key at console.groq.com)")
        elif provider == "gemini" and not self.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY is not set (get free key at aistudio.google.com)")
        elif provider == "ollama":
            pass  # no key needed

        return errors

    @property
    def notion_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.NOTION_API_TOKEN}",
            "Notion-Version": self.NOTION_VERSION,
            "Content-Type": "application/json",
        }


config = Config()
