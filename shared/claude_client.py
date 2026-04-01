"""
Thin wrapper around the Anthropic client.
Use complete() for plain text, complete_json() when you expect a JSON response.
"""
import json
import re

import anthropic

from shared.config import ANTHROPIC_API_KEY, CLAUDE_MODEL

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def complete(prompt: str, max_tokens: int = 800, model: str | None = None) -> str:
    """Send a single-turn prompt and return the response text."""
    response = get_client().messages.create(
        model=model or CLAUDE_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def complete_json(prompt: str, max_tokens: int = 800, model: str | None = None) -> dict:
    """Send a prompt expecting a JSON response. Strips markdown fences if present."""
    text = complete(prompt, max_tokens=max_tokens, model=model)
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return json.loads(text)
