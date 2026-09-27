from __future__ import annotations

from typing import Protocol

from app.llm.schemas import (
    LLMChoiceDecision,
    LLMMediationDecision,
    SafeChoice,
)


class LLMProvider(Protocol):
    model: str

    async def choose(
        self,
        *,
        task: str,
        context: dict,
        options: list[SafeChoice],
    ) -> LLMChoiceDecision:
        ...

    async def mediate(
        self,
        *,
        context: dict,
    ) -> LLMMediationDecision:
        ...
