from __future__ import annotations

import json

from app.llm.prompts import (
    CHOICE_SYSTEM_PROMPT,
    MEDIATION_SYSTEM_PROMPT,
)
from app.llm.schemas import (
    LLMChoiceDecision,
    LLMMediationDecision,
    SafeChoice,
)


class OpenAIProvider:
    """
    Thin adapter around the official OpenAI Python SDK.

    The import is intentionally local so the application can still boot in
    deterministic mode when the optional `openai` package is not installed.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_retries: int,
    ) -> None:
        from openai import AsyncOpenAI

        self.model = model
        self.client = AsyncOpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=max_retries,
        )

    async def choose(
        self,
        *,
        task: str,
        context: dict,
        options: list[SafeChoice],
    ) -> LLMChoiceDecision:
        payload = {
            "task": task,
            "context": context,
            "allowed_choices": [
                item.model_dump(mode="json")
                for item in options
            ],
        }

        response = await self.client.responses.parse(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": CHOICE_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        payload,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                },
            ],
            text_format=LLMChoiceDecision,
        )

        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError(
                "OpenAI returned no parsed structured decision."
            )

        return parsed

    async def mediate(
        self,
        *,
        context: dict,
    ) -> LLMMediationDecision:
        response = await self.client.responses.parse(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": MEDIATION_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": (
                                "Suggest a public bilateral compromise "
                                "or recommend coalition fallback."
                            ),
                            "context": context,
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                },
            ],
            text_format=LLMMediationDecision,
        )

        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError(
                "OpenAI returned no parsed mediation result."
            )

        return parsed
