"""DeepSeek LLM wrapper — thin, cheap, reliable."""

from __future__ import annotations

import json
import logging
import os
import time

log = logging.getLogger("maxim.llm")

_client = None


def _get_client():
    global _client
    if _client is None:
        try:
            import openai
        except ImportError:
            raise RuntimeError("pip install openai")
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY not set")
        _client = openai.OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    return _client


def call(
    system: str,
    user: str,
    json_mode: bool = True,
    max_tokens: int = 2048,
    retries: int = 3,
) -> str:
    """Call DeepSeek API. Returns response text."""
    client = _get_client()
    kwargs = {
        "model": "deepseek-chat",
        "max_tokens": max_tokens,
        "temperature": 0.8,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(**kwargs)
            text = resp.choices[0].message.content.strip()
            return text
        except Exception as e:
            log.warning("LLM call failed (attempt %d/%d): %s", attempt + 1, retries, e)
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    return "{}"


def call_json(system: str, user: str, max_tokens: int = 2048) -> dict:
    """Call DeepSeek and parse JSON response."""
    raw = call(system, user, json_mode=True, max_tokens=max_tokens)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        log.warning("Failed to parse JSON from LLM: %s", raw[:200])
        return {}
