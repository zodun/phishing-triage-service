from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Label = Literal["phishing", "legit", "suspicious"]


class ClassifyRequest(BaseModel):
    text: str = Field(min_length=1, max_length=40000, description="Raw email text (headers + body)")


class Classification(BaseModel):
    """The structured output the model must produce."""

    label: Label
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(max_length=600)
    indicators: list[str] = Field(default_factory=list)


class GuardTrip(BaseModel):
    stage: str  # "input" | "output"
    code: str
    detail: str = ""


class ClassifyResponse(BaseModel):
    label: Label
    confidence: float
    reason: str
    indicators: list[str]
    request_id: str
    model: str
    latency_ms: float
    guardrails: list[GuardTrip] = Field(default_factory=list)
    usage: dict[str, int] = Field(default_factory=dict)
