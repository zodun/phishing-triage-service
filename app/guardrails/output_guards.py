from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.schemas import Classification, GuardTrip

# Rough "this looks like a credential/secret" detector - the model should never
# echo one of these back in its reason/indicators.
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


@dataclass
class OutputGuardResult:
    classification: Classification
    trips: list[GuardTrip] = field(default_factory=list)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def check_classification(result: Classification, *, email_text: str) -> OutputGuardResult:
    """Vet the model's structured output.

    - Drop any `indicators` entry that is not actually quoted from the email
      (catches invented URLs / IOCs).
    - Scrub secret-looking strings out of `reason` / `indicators`.
    """
    trips: list[GuardTrip] = []
    haystack = _norm(email_text)

    kept: list[str] = []
    invented: list[str] = []
    for ind in result.indicators:
        if ind.strip() and _norm(ind) in haystack:
            kept.append(ind)
        else:
            invented.append(ind)
    if invented:
        trips.append(
            GuardTrip(
                stage="output",
                code="invented_indicator",
                detail=f"removed {len(invented)} indicator(s) not present in the email",
            )
        )

    reason = result.reason
    for pattern in [*_SECRET_PATTERNS]:
        if pattern.search(reason) or any(pattern.search(i) for i in kept):
            reason = pattern.sub("[REDACTED_SECRET]", reason)
            kept = [pattern.sub("[REDACTED_SECRET]", i) for i in kept]
            trips.append(
                GuardTrip(stage="output", code="secret_leak", detail="secret-like string scrubbed")
            )

    cleaned = Classification(
        label=result.label,
        confidence=result.confidence,
        reason=reason,
        indicators=kept,
    )
    return OutputGuardResult(cleaned, trips)
