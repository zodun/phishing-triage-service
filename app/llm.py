from __future__ import annotations

import time
from dataclasses import dataclass, field

from openai import OpenAI

from app.config import Settings


@dataclass
class LLMResult:
    text: str
    model: str
    latency_ms: float
    usage: dict[str, int] = field(default_factory=dict)


class LLMClient:
    """Wrapper around DeepSeek's OpenAI-compatible chat API, with a deterministic
    fake used when LLM_FAKE=true so tests and CI never hit the network."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._fake = settings.llm_fake
        self._client: OpenAI | None = None
        if not self._fake:
            self._client = OpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.base_url,
                timeout=settings.request_timeout_s,
            )

    def generate(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> LLMResult:
        model = model or self._settings.primary_model
        max_tokens = max_tokens or self._settings.max_output_tokens
        start = time.perf_counter()

        if self._fake or self._client is None:
            return LLMResult(
                text=_fake_completion(system, user),
                model=f"fake:{model}",
                latency_ms=_elapsed_ms(start),
                usage={"input_tokens": 0, "output_tokens": 0},
            )

        resp = self._client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        text = (resp.choices[0].message.content or "").strip()
        usage = {
            "input_tokens": resp.usage.prompt_tokens if resp.usage else 0,
            "output_tokens": resp.usage.completion_tokens if resp.usage else 0,
        }
        return LLMResult(text=text, model=model, latency_ms=_elapsed_ms(start), usage=usage)


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


def _fake_completion(system: str, user: str) -> str:
    """Deterministic stand-in for LLM_FAKE=true. Rough keyword heuristic so the
    pipeline and tests exercise all three labels without a network call."""
    low = user.lower()
    if any(w in low for w in ("password", "verify your account", "bank details", "gift card")):
        label, conf = "phishing", 0.9
    elif any(w in low for w in ("receipt", "invoice #", "unsubscribe", "calendar invite")):
        label, conf = "legit", 0.85
    else:
        label, conf = "suspicious", 0.5
    return (
        f'{{"label": "{label}", "confidence": {conf}, '
        f'"reason": "fake classifier ({label})", "indicators": []}}'
    )
