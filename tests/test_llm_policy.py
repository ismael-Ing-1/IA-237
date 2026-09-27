import asyncio

from app.llm.config import LLMConfig, LLMMode
from app.llm.policy import LLMPolicy
from app.llm.schemas import (
    LLMChoiceDecision,
    LLMMediationDecision,
    SafeChoice,
)


class FakeProvider:
    model = "fake-model"

    def __init__(self, choice_id="reject"):
        self.choice_id = choice_id

    async def choose(self, *, task, context, options):
        return LLMChoiceDecision(
            choice_id=self.choice_id,
            reason="fake",
            confidence=0.9,
        )

    async def mediate(self, *, context):
        return LLMMediationDecision(
            action="suggest_coalition",
            reason="fake",
        )


def test_shadow_never_changes_effective_choice():
    policy = LLMPolicy(
        config=LLMConfig(
            mode=LLMMode.SHADOW,
            model="fake-model",
        ),
        provider=FakeProvider("reject"),
    )

    outcome = asyncio.run(
        policy.choose(
            task="test",
            context={},
            options=[
                SafeChoice(
                    choice_id="counter",
                    label="Counter",
                    description="safe",
                ),
                SafeChoice(
                    choice_id="reject",
                    label="Reject",
                    description="safe",
                ),
            ],
            fallback_choice_id="counter",
        )
    )

    assert outcome.model_choice_id == "reject"
    assert outcome.effective_choice_id == "counter"


def test_active_accepts_only_allowed_choice():
    policy = LLMPolicy(
        config=LLMConfig(
            mode=LLMMode.ACTIVE,
            model="fake-model",
        ),
        provider=FakeProvider("reject"),
    )

    outcome = asyncio.run(
        policy.choose(
            task="test",
            context={},
            options=[
                SafeChoice(
                    choice_id="counter",
                    label="Counter",
                    description="safe",
                ),
                SafeChoice(
                    choice_id="reject",
                    label="Reject",
                    description="safe",
                ),
            ],
            fallback_choice_id="counter",
        )
    )

    assert outcome.effective_choice_id == "reject"
    assert not outcome.used_fallback


def test_active_invalid_choice_falls_back():
    policy = LLMPolicy(
        config=LLMConfig(
            mode=LLMMode.ACTIVE,
            model="fake-model",
        ),
        provider=FakeProvider("invented_action"),
    )

    outcome = asyncio.run(
        policy.choose(
            task="test",
            context={},
            options=[
                SafeChoice(
                    choice_id="counter",
                    label="Counter",
                    description="safe",
                ),
            ],
            fallback_choice_id="counter",
        )
    )

    assert outcome.effective_choice_id == "counter"
    assert outcome.used_fallback
