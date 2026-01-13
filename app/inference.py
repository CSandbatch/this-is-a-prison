from __future__ import annotations

from dataclasses import dataclass

from openai_inference import responses_text

from .storage import ContextEntry


@dataclass(frozen=True)
class InferenceResult:
    reply_text: str


def run_inference(
    *,
    openai_api_key: str,
    model: str,
    system_prompt: str,
    context: list[ContextEntry],
    temperature: float = 0.5,
    max_output_tokens: int = 512,
    timeout_s: float = 15.0,
) -> InferenceResult:
    messages = [{"role": "system", "content": system_prompt}]
    for entry in context:
        if entry.role not in {"user", "assistant"}:
            continue
        if not entry.content:
            continue
        messages.append({"role": entry.role, "content": entry.content})

    text = responses_text(
        api_key=openai_api_key,
        model=model,
        messages=messages,
        reasoning_effort="none",
        verbosity="medium",
        temperature=min(max(temperature, 0.0), 0.5),
        max_output_tokens=max_output_tokens,
        timeout_s=timeout_s,
    )
    if not text:
        text = "Inference error. Try again."
    return InferenceResult(reply_text=text)
