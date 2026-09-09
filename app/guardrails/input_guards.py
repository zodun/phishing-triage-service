from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.schemas import GuardTrip

# Phrases that look like an attempt to steer the classifier rather than normal
# email content. For this service we do NOT block on these - a phishing email
# that also contains an injection payload should still be caught - we flag it,
# isolate the email in the prompt, and tell the model to ignore instructions
# found inside it.
_INJECTION_PATTERNS = [
    re.compile(r"ignore (all |any |the )?(previous|prior|above) (instructions|prompts?)", re.I),
    re.compile(r"disregard (the )?(system|previous|above) (prompt|instructions)", re.I),
    re.compile(r"you are (now )?(a|an) [\w -]+ (assistant|model|ai)", re.I),
    re.compile(r"classify (this|the) (email|message) as (legit|safe|benign)", re.I),
    re.compile(r"(reveal|print|show|repeat) (me )?(your |the )?(system prompt|instructions)", re.I),
]


@dataclass
class InputGuardResult:
    allowed: bool
    text: str
    trips: list[GuardTrip] = field(default_factory=list)


def check_email(text: str, *, max_chars: int) -> InputGuardResult:
    """Validate an inbound email. Hard-reject only empty / oversized input;
    flag (do not block) prompt-injection-looking content."""
    body = text.strip()

    if not body:
        return InputGuardResult(
            False, body, [GuardTrip(stage="input", code="empty", detail="empty email")]
        )
    if len(body) > max_chars:
        return InputGuardResult(
            False,
            body[:max_chars],
            [GuardTrip(stage="input", code="too_long", detail=f"{len(body)} > {max_chars} chars")],
        )

    trips: list[GuardTrip] = []
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(body):
            trips.append(
                GuardTrip(
                    stage="input",
                    code="injection_attempt",
                    detail="email contains text aimed at steering the classifier",
                )
            )
            break
    return InputGuardResult(True, body, trips)
