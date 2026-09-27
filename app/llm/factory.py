from __future__ import annotations

import os

from app.llm.config import (
    LLMConfig,
    LLMMode,
)
from app.llm.policy import LLMPolicy


def build_llm_policy() -> LLMPolicy:
    config = LLMConfig.from_env()

    if config.mode == LLMMode.DISABLED:
        return LLMPolicy(
            config=config,
            provider=None,
            unavailable_reason="disabled",
        )

    api_key = os.getenv(
        "OPENAI_API_KEY",
        "",
    ).strip()

    if not api_key:
        return LLMPolicy(
            config=config,
            provider=None,
            unavailable_reason=(
                "OPENAI_API_KEY is not configured."
            ),
        )

    try:
        from app.llm.openai_provider import (
            OpenAIProvider,
        )

        provider = OpenAIProvider(
            api_key=api_key,
            model=config.model,
            timeout_seconds=(
                config.timeout_seconds
            ),
            max_retries=config.max_retries,
        )
    except Exception as exc:
        return LLMPolicy(
            config=config,
            provider=None,
            unavailable_reason=(
                f"Provider initialization failed: "
                f"{type(exc).__name__}"
            ),
        )

    return LLMPolicy(
        config=config,
        provider=provider,
    )
