from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.llm.config import LLMMode


class SafeChoice(BaseModel):
    """
    An option already validated by local deterministic code.

    description must never contain raw private limits or exact private
    inventory that has not already been made public.
    """

    model_config = ConfigDict(extra="forbid")

    choice_id: str
    label: str
    description: str
    public_terms: dict = Field(
        default_factory=dict
    )


class LLMChoiceDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    choice_id: str
    reason: str = Field(min_length=1, max_length=600)
    confidence: float = Field(ge=0, le=1)


class LLMChoiceOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: LLMMode
    model: str
    effective_choice_id: str
    model_choice_id: str | None = None
    reason: str
    confidence: float | None = None
    used_fallback: bool = False
    fallback_reason: str | None = None


class LLMResourceLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_type: str = Field(min_length=1)
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1)


class LLMMediationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal[
        "suggest_counter",
        "suggest_coalition",
    ]

    reason: str = Field(min_length=1, max_length=800)

    sender_id: str | None = None
    receiver_id: str | None = None

    offered_resources: list[
        LLMResourceLine
    ] = Field(default_factory=list)

    requested_resources: list[
        LLMResourceLine
    ] = Field(default_factory=list)


class LLMMediationOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: LLMMode
    model: str
    suggestion: LLMMediationDecision | None = None
    error: str | None = None
