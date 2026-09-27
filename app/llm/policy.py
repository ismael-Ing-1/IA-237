from __future__ import annotations

import logging
from typing import Any

from app.llm.config import (
    LLMConfig,
    LLMMode,
)
from app.llm.provider import LLMProvider
from app.llm.schemas import (
    LLMChoiceOutcome,
    LLMMediationOutcome,
    SafeChoice,
)

logger = logging.getLogger(__name__)


class LLMPolicy:
    """
    Safe policy wrapper.

    The provider can suggest decisions, but only Python decides whether the
    returned choice is one of the allowed options.

    In SHADOW mode the model is observed but never controls business state.
    """

    def __init__(
        self,
        *,
        config: LLMConfig,
        provider: LLMProvider | None = None,
        unavailable_reason: str | None = None,
    ) -> None:
        self.config = config
        self.provider = provider
        self.unavailable_reason = (
            unavailable_reason
        )

    @property
    def mode(self) -> LLMMode:
        return self.config.mode

    @property
    def should_call(self) -> bool:
        return (
            self.config.mode
            in {
                LLMMode.SHADOW,
                LLMMode.ACTIVE,
            }
            and self.provider is not None
        )

    def status(self) -> dict[str, Any]:
        return {
            "mode": self.config.mode.value,
            "model": self.config.model,
            "available": self.provider is not None,
            "provider": (
                "openai"
                if self.provider is not None
                else None
            ),
            "unavailable_reason": (
                self.unavailable_reason
            ),
        }

    async def choose(
        self,
        *,
        task: str,
        context: dict,
        options: list[SafeChoice],
        fallback_choice_id: str,
    ) -> LLMChoiceOutcome:
        option_ids = {
            item.choice_id
            for item in options
        }

        if fallback_choice_id not in option_ids:
            raise ValueError(
                "Fallback choice is not in safe options."
            )

        if self.config.mode == LLMMode.DISABLED:
            return LLMChoiceOutcome(
                mode=self.config.mode,
                model=self.config.model,
                effective_choice_id=(
                    fallback_choice_id
                ),
                reason=(
                    "LLM disabled; deterministic "
                    "policy used."
                ),
                used_fallback=True,
                fallback_reason="disabled",
            )

        if self.provider is None:
            return LLMChoiceOutcome(
                mode=self.config.mode,
                model=self.config.model,
                effective_choice_id=(
                    fallback_choice_id
                ),
                reason=(
                    "LLM unavailable; deterministic "
                    "policy used."
                ),
                used_fallback=True,
                fallback_reason=(
                    self.unavailable_reason
                    or "provider unavailable"
                ),
            )

        try:
            decision = await self.provider.choose(
                task=task,
                context=context,
                options=options,
            )
        except Exception as exc:
            logger.warning(
                "LLM choice failed for task %s: %s",
                task,
                exc,
            )
            return LLMChoiceOutcome(
                mode=self.config.mode,
                model=self.config.model,
                effective_choice_id=(
                    fallback_choice_id
                ),
                reason=(
                    "LLM call failed; deterministic "
                    "policy used."
                ),
                used_fallback=True,
                fallback_reason=type(exc).__name__,
            )

        if decision.choice_id not in option_ids:
            return LLMChoiceOutcome(
                mode=self.config.mode,
                model=self.config.model,
                effective_choice_id=(
                    fallback_choice_id
                ),
                model_choice_id=decision.choice_id,
                reason=decision.reason,
                confidence=decision.confidence,
                used_fallback=True,
                fallback_reason=(
                    "Model selected a choice outside "
                    "the locally allowed set."
                ),
            )

        effective = (
            decision.choice_id
            if self.config.mode == LLMMode.ACTIVE
            else fallback_choice_id
        )

        return LLMChoiceOutcome(
            mode=self.config.mode,
            model=self.config.model,
            effective_choice_id=effective,
            model_choice_id=decision.choice_id,
            reason=decision.reason,
            confidence=decision.confidence,
            used_fallback=(
                self.config.mode
                != LLMMode.ACTIVE
            ),
            fallback_reason=(
                "shadow mode"
                if self.config.mode
                == LLMMode.SHADOW
                else None
            ),
        )

    async def mediate(
        self,
        *,
        context: dict,
    ) -> LLMMediationOutcome:
        if self.config.mode == LLMMode.DISABLED:
            return LLMMediationOutcome(
                mode=self.config.mode,
                model=self.config.model,
                error="disabled",
            )

        if self.provider is None:
            return LLMMediationOutcome(
                mode=self.config.mode,
                model=self.config.model,
                error=(
                    self.unavailable_reason
                    or "provider unavailable"
                ),
            )

        try:
            suggestion = await self.provider.mediate(
                context=context,
            )
        except Exception as exc:
            logger.warning(
                "LLM mediation failed: %s",
                exc,
            )
            return LLMMediationOutcome(
                mode=self.config.mode,
                model=self.config.model,
                error=type(exc).__name__,
            )

        return LLMMediationOutcome(
            mode=self.config.mode,
            model=self.config.model,
            suggestion=suggestion,
        )
