from __future__ import annotations

import math
import os
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class LLMMode(str, Enum):
    DISABLED = "disabled"
    SHADOW = "shadow"
    ACTIVE = "active"


class LLMConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: LLMMode = LLMMode.DISABLED
    model: str = "gpt-6-astra"
    timeout_seconds: float = Field(default=6.0, gt=0, le=30)
    max_retries: int = Field(default=0, ge=0, le=3)
    max_candidates: int = Field(default=6, ge=1, le=20)

    @classmethod
    def from_env(cls) -> "LLMConfig":
        raw_mode = os.getenv("LLM_MODE", "disabled").strip().lower()
        try:
            mode = LLMMode(raw_mode)
        except ValueError as exc:
            raise ValueError(
                "LLM_MODE must be disabled, shadow or active."
            ) from exc

        timeout = float(
            os.getenv("OPENAI_TIMEOUT_SECONDS", "6")
        )
        if not math.isfinite(timeout):
            raise ValueError(
                "OPENAI_TIMEOUT_SECONDS must be finite."
            )

        return cls(
            mode=mode,
            model=os.getenv(
                "OPENAI_MODEL",
                "gpt-6-astra",
            ).strip(),
            timeout_seconds=timeout,
            max_retries=int(
                os.getenv(
                    "OPENAI_MAX_RETRIES",
                    "0",
                )
            ),
            max_candidates=int(
                os.getenv(
                    "LLM_MAX_CANDIDATES",
                    "6",
                )
            ),
        )
