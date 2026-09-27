# app/agents/mediator_agent.py

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.models import (
    Negotiation,
    NegotiationStatus,
    Resource,
    ResourceRequest,
)


class MediationAction(str, Enum):
    NO_ACTION = "no_action"
    SUGGEST_COUNTER = "suggest_counter"
    SUGGEST_COALITION = "suggest_coalition"


class MediationTrigger(str, Enum):
    """Reason for consulting the mediator."""

    REPEATED_COUNTERS = "repeated_counters"
    ROUND_PRESSURE = "round_pressure"
    MANUAL = "manual"


class MediationProposal(BaseModel):
    """
    Public compromise produced from already revealed offers.

    The mediator never sends or accepts this proposal.
    """

    sender_id: str
    receiver_id: str

    offered_resources: list[Resource] = Field(
        default_factory=list
    )

    requested_resources: list[ResourceRequest] = Field(
        default_factory=list
    )


class MediationEvaluation(BaseModel):
    """
    Private PersonalAgent verdict about a public mediator proposal.

    Private limits are intentionally not included in this model.
    """

    user_id: str
    accepted: bool
    reason: str


class MediationResult(BaseModel):
    action: MediationAction
    reason: str
    proposal: MediationProposal | None = None
    trigger: MediationTrigger | None = None


class MediatorAgent:
    """
    Bilateral mediator.

    It:
    - reads only public offers;
    - never reads private constraints;
    - never mutates Negotiation;
    - never accepts or executes a deal.
    """

    TERMINAL_STATES = {
        NegotiationStatus.AGREEMENT_FOUND,
        NegotiationStatus.WAITING_HUMAN,
        NegotiationStatus.APPROVED,
        NegotiationStatus.REJECTED,
        NegotiationStatus.CANCELLED,
        NegotiationStatus.FAILED,
    }

    def __init__(
        self,
        *,
        minimum_offers: int = 4,
        round_pressure_buffer: int = 2,
    ) -> None:
        if minimum_offers < 2:
            raise ValueError(
                "minimum_offers must be at least 2."
            )

        if round_pressure_buffer < 1:
            raise ValueError(
                "round_pressure_buffer must be positive."
            )

        self.minimum_offers = minimum_offers
        self.round_pressure_buffer = round_pressure_buffer

    def intervention_trigger(
        self,
        negotiation: Negotiation,
    ) -> MediationTrigger | None:
        """
        Let PersonalAgents negotiate first.

        Automatic mediation begins only after both sides have already
        countered repeatedly, or when the round limit approaches.
        """

        if negotiation.status in self.TERMINAL_STATES:
            return None

        offers = negotiation.offers

        if len(offers) < 2:
            return None

        previous = offers[-2]
        latest = offers[-1]

        if not (
            previous.sender_id == latest.receiver_id
            and previous.receiver_id == latest.sender_id
        ):
            return None

        counter_senders = {
            offer.sender_id
            for offer in offers
            if offer.parent_offer_id is not None
        }

        participants = set(
            negotiation.participant_ids
        )

        if (
            len(offers) >= self.minimum_offers
            and participants
            and participants.issubset(counter_senders)
        ):
            return MediationTrigger.REPEATED_COUNTERS

        threshold = max(
            2,
            negotiation.max_rounds
            - self.round_pressure_buffer,
        )

        if negotiation.current_round >= threshold:
            return MediationTrigger.ROUND_PRESSURE

        return None

    def should_intervene(
        self,
        negotiation: Negotiation,
    ) -> bool:
        return (
            self.intervention_trigger(negotiation)
            is not None
        )

    def mediate(
        self,
        negotiation: Negotiation,
        *,
        trigger: MediationTrigger | None = None,
    ) -> MediationResult:
        """
        Inspect the last two public offers and propose a midpoint.

        The result is advice only. PersonalAgents must privately
        evaluate the proposal afterwards.
        """

        if negotiation.status in self.TERMINAL_STATES:
            return MediationResult(
                action=MediationAction.NO_ACTION,
                reason=(
                    "Negotiation is already finished "
                    "or waiting for approval."
                ),
                trigger=trigger,
            )

        if len(negotiation.offers) < 2:
            return MediationResult(
                action=MediationAction.NO_ACTION,
                reason=(
                    "At least two public offers are required "
                    "before mediation is useful."
                ),
                trigger=trigger,
            )

        previous = negotiation.offers[-2]
        latest = negotiation.offers[-1]

        if not (
            previous.sender_id == latest.receiver_id
            and previous.receiver_id == latest.sender_id
        ):
            return MediationResult(
                action=MediationAction.SUGGEST_COALITION,
                reason=(
                    "The public offer sequence is not suitable "
                    "for a bilateral compromise."
                ),
                trigger=trigger,
            )

        proposal = self._build_midpoint_proposal(
            previous,
            latest,
        )

        if proposal is None:
            return MediationResult(
                action=MediationAction.SUGGEST_COALITION,
                reason=(
                    "No bilateral midpoint could be constructed "
                    "from the public offers."
                ),
                trigger=trigger,
            )

        return MediationResult(
            action=MediationAction.SUGGEST_COUNTER,
            reason=(
                "A public midpoint compromise was generated "
                "after repeated negotiation."
            ),
            proposal=proposal,
            trigger=trigger,
        )

    def _build_midpoint_proposal(
        self,
        previous,
        latest,
    ) -> MediationProposal | None:
        """
        Example:

            Alice : 10 STORAGE for 8 H100
            Bob   : 8 H100 for 16 STORAGE

        The next sender is Alice and the public midpoint is:

            13 STORAGE for 8 H100
        """

        next_sender = latest.receiver_id
        next_receiver = latest.sender_id

        offered_resources: list[Resource] = []

        for previous_resource in previous.offered_resources:
            matching = next(
                (
                    item
                    for item in latest.requested_resources
                    if (
                        item.resource_type
                        == previous_resource.resource_type
                        and item.unit == previous_resource.unit
                    )
                ),
                None,
            )

            if matching is None:
                continue

            midpoint = (
                previous_resource.quantity
                + matching.quantity
            ) / 2

            if midpoint <= 0:
                continue

            offered_resources.append(
                Resource(
                    resource_type=previous_resource.resource_type,
                    quantity=round(midpoint, 3),
                    unit=previous_resource.unit,
                    attributes=dict(
                        previous_resource.attributes
                    ),
                )
            )

        requested_resources: list[ResourceRequest] = []

        for previous_request in previous.requested_resources:
            matching = next(
                (
                    item
                    for item in latest.offered_resources
                    if (
                        item.resource_type
                        == previous_request.resource_type
                        and item.unit == previous_request.unit
                    )
                ),
                None,
            )

            if matching is None:
                continue

            midpoint = (
                previous_request.quantity
                + matching.quantity
            ) / 2

            if midpoint <= 0:
                continue

            requested_resources.append(
                ResourceRequest(
                    resource_type=previous_request.resource_type,
                    quantity=round(midpoint, 3),
                    unit=previous_request.unit,
                    deadline=previous_request.deadline,
                    attributes=dict(
                        previous_request.attributes
                    ),
                )
            )

        if not offered_resources or not requested_resources:
            return None

        return MediationProposal(
            sender_id=next_sender,
            receiver_id=next_receiver,
            offered_resources=offered_resources,
            requested_resources=requested_resources,
        )
