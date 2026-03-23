"""Unified LLM interface — supports Groq (free), Gemini (free), Ollama (free/local), Anthropic (paid)."""

from __future__ import annotations

import json
import re
import httpx

from notion_reverse_autopilot.config import config


class LLMClient:
    """Single interface to call any supported LLM provider."""

    def __init__(self):
        self.provider = config.AI_PROVIDER
        self.model = config.ai_model

    def ask(self, prompt: str, max_tokens: int = 4096) -> str:
        """Send a prompt and get a text response."""
        if self.provider == "groq":
            return self._call_groq(prompt, max_tokens)
        elif self.provider == "gemini":
            return self._call_gemini(prompt, max_tokens)
        elif self.provider == "ollama":
            return self._call_ollama(prompt, max_tokens)
        elif self.provider == "anthropic":
            return self._call_anthropic(prompt, max_tokens)
        else:
            raise ValueError(f"Unknown AI_PROVIDER: {self.provider}")

    def ask_json(self, prompt: str, max_tokens: int = 8192) -> dict:
        """Send a prompt and parse the response as JSON. Handles truncated/malformed responses."""
        raw = self.ask(prompt, max_tokens)
        text = raw.strip()

        # Strip markdown code fences
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        # Attempt 1: direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Attempt 2: extract JSON object from response
        start = text.find("{")
        if start >= 0:
            # Try to find the matching closing brace
            end = text.rfind("}") + 1
            if end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass

            # Attempt 3: fix truncated JSON by closing open structures
            fragment = text[start:]
            repaired = self._repair_json(fragment)
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass

        return {}

    def _repair_json(self, text: str) -> str:
        """Attempt to repair truncated JSON by closing open brackets/braces."""
        # Remove any trailing incomplete string (unterminated quote)
        # Find the last complete key-value pair
        last_good = len(text)
        in_string = False
        escape = False
        for i, ch in enumerate(text):
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"':
                in_string = not in_string

        # If we ended inside a string, truncate to last comma or bracket before it
        if in_string:
            # Find the last quote that opened this string
            last_quote = text.rfind('"')
            if last_quote > 0:
                # Go back to the last comma, bracket, or brace
                truncate_at = max(
                    text.rfind(',', 0, last_quote),
                    text.rfind('[', 0, last_quote),
                    text.rfind('{', 0, last_quote),
                )
                if truncate_at > 0:
                    text = text[:truncate_at]

        # Count open brackets and braces, close them
        open_braces = text.count('{') - text.count('}')
        open_brackets = text.count('[') - text.count(']')

        # Remove trailing comma if present
        text = text.rstrip().rstrip(',')

        text += ']' * max(0, open_brackets)
        text += '}' * max(0, open_braces)

        return text

    # ── Providers ────────────────────────────────────────────────

    def _call_groq(self, prompt: str, max_tokens: int) -> str:
        resp = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {config.GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.3,
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def _call_gemini(self, prompt: str, max_tokens: int) -> str:
        resp = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            params={"key": config.GEMINI_API_KEY},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": max_tokens,
                    "temperature": 0.3,
                    "responseMimeType": "application/json",
                },
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]

    def _call_ollama(self, prompt: str, max_tokens: int) -> str:
        resp = httpx.post(
            f"{config.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": max_tokens, "temperature": 0.3},
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        return resp.json()["response"]

    def _call_anthropic(self, prompt: str, max_tokens: int) -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
