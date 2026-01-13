from __future__ import annotations

from typing import Any, Iterable

from openai import OpenAI


def chat_completion_text(
    *,
    api_key: str,
    model: str,
    messages: Iterable[dict[str, Any]],
    temperature: float,
    max_tokens: int,
    timeout_s: float,
) -> str:
    client = OpenAI(api_key=api_key, timeout=timeout_s, max_retries=1)
    resp = client.chat.completions.create(
        model=model,
        messages=list(messages),
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return (resp.choices[0].message.content or "").strip()

