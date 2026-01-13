from __future__ import annotations

from typing import Any, Iterable, Optional

from openai import OpenAI


def _extract_output_text(resp: Any) -> str:
    output_text = getattr(resp, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    as_dict: Optional[dict[str, Any]] = None
    try:
        as_dict = resp.model_dump()  # pydantic-style
    except Exception:
        try:
            as_dict = dict(resp)  # type: ignore[arg-type]
        except Exception:
            as_dict = None

    if isinstance(as_dict, dict):
        out = as_dict.get("output")
        if isinstance(out, list):
            chunks: list[str] = []
            for item in out:
                if not isinstance(item, dict):
                    continue
                content = item.get("content")
                if not isinstance(content, list):
                    continue
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    if part.get("type") in {"output_text", "text"} and isinstance(part.get("text"), str):
                        chunks.append(part["text"])
            joined = "\n".join([c.strip() for c in chunks if c.strip()]).strip()
            if joined:
                return joined

    return ""


def responses_text(
    *,
    api_key: str,
    model: str,
    messages: Iterable[dict[str, Any]],
    reasoning_effort: str = "none",
    verbosity: str = "medium",
    temperature: float = 0.5,
    max_output_tokens: int = 512,
    timeout_s: float = 15.0,
) -> str:
    client = OpenAI(api_key=api_key, timeout=timeout_s, max_retries=1)
    resp = client.responses.create(
        model=model,
        input=list(messages),
        reasoning={"effort": reasoning_effort},
        text={"verbosity": verbosity},
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )
    return _extract_output_text(resp).strip()

