"""Guardrails: data masking, prompt-injection detection, output validation and control limits."""
from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator

from .config import SETTINGS

INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior) instructions", r"disregard .*instructions", r"you are now",
    r"system prompt", r"close (this|the) break", r"auto[- ]?approve", r"do not escalate",
]


def detect_injection(text: str) -> bool:
    t = (text or "").lower()
    return any(re.search(p, t) for p in INJECTION_PATTERNS)


class Masker:
    """Replaces client / counterparty names and account numbers with stable tokens before LLM calls."""

    def __init__(self, names: list[str]):
        self.map = {n: f"CLIENT_{i:03d}" for i, n in enumerate(sorted(set(names)), start=1)}

    def mask(self, text: str) -> str:
        if not text:
            return text
        for name, tok in self.map.items():
            text = re.sub(re.escape(name), tok, text, flags=re.IGNORECASE)
        return re.sub(r"\b\d{8,12}\b", "ACCT_****", text)


class Investigation(BaseModel):
    """Schema every LLM answer must satisfy; anything else is rejected and rules are used instead."""
    category: str
    confidence: float = Field(ge=0, le=1)
    root_cause: str = Field(min_length=5, max_length=600)
    recommended_action: str = Field(min_length=5, max_length=600)
    citations: list[str] = Field(default_factory=list)
    query_to_correspondent: Optional[str] = None

    @field_validator("category")
    @classmethod
    def known_category(cls, v):
        if v not in SETTINGS.allowed_categories:
            raise ValueError(f"unknown category {v}")
        return v


def validate_llm_output(data: dict) -> tuple[Optional[Investigation], Optional[str]]:
    try:
        return Investigation(**data), None
    except ValidationError as e:
        return None, str(e).splitlines()[0]


Decision = Literal["AUTO_RESOLVE", "MAKER_PROPOSAL", "ESCALATE"]


def control_decision(category: str, amount: float, confidence: float, injection: bool) -> tuple[Decision, str]:
    """Policy POL-NR-03: what the agent is allowed to do on its own."""
    if injection or category == "SUSPICIOUS":
        return "ESCALATE", "Suspicious item or instruction-like text in narrative: escalate to Team Lead and FCC."
    if amount >= SETTINGS.escalation_amount:
        return "ESCALATE", f"Amount >= escalation limit {SETTINGS.escalation_amount:,.0f}."
    if (category in SETTINGS.auto_action_categories and abs(amount) <= SETTINGS.auto_action_max_amount
            and confidence >= SETTINGS.auto_action_min_confidence):
        return "AUTO_RESOLVE", "Within auto-action category, amount and confidence limits."
    return "MAKER_PROPOSAL", "Requires checker (human) approval under four-eyes principle."
