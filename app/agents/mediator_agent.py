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


class MediationProposal(BaseModel):
    """
    Proposition publique produite par le médiateur.

    Le médiateur NE l'envoie pas lui-même
    et ne l'accepte jamais.
    """

    sender_id: str

    receiver_id: str

    offered_resources: list[
        Resource
    ] = Field(
        default_factory=list
    )

    requested_resources: list[
        ResourceRequest
    ] = Field(
        default_factory=list
    )


class MediationResult(BaseModel):

    action: MediationAction

    reason: str

    proposal: MediationProposal | None = None


class MediatorAgent:
    """
    Agent spécialisé dans les négociations bloquées.

    Règles :

    - aucune lecture des contraintes privées ;
    - aucune acceptation automatique ;
    - aucune modification de Negotiation ;
    - produit uniquement une suggestion.
    """

    TERMINAL_STATES = {
        NegotiationStatus.AGREEMENT_FOUND,
        NegotiationStatus.WAITING_HUMAN,
        NegotiationStatus.APPROVED,
        NegotiationStatus.REJECTED,
        NegotiationStatus.CANCELLED,
        NegotiationStatus.FAILED,
    }

    def mediate(
        self,
        negotiation: Negotiation,
    ) -> MediationResult:
        """
        Examine les deux dernières offres.

        Si elles sont compatibles, propose un compromis
        basé sur les informations PUBLIQUES déjà révélées.
        """

        if negotiation.status in self.TERMINAL_STATES:

            return MediationResult(
                action=MediationAction.NO_ACTION,

                reason=(
                    "Negotiation is already finished "
                    "or waiting for approval."
                ),
            )

        if len(negotiation.offers) < 2:

            return MediationResult(
                action=MediationAction.NO_ACTION,

                reason=(
                    "At least two offers are required "
                    "before mediation is useful."
                ),
            )

        previous = negotiation.offers[-2]
        latest = negotiation.offers[-1]

        # Les deux offres doivent représenter
        # une vraie séquence de contre-offres.
        if not (
            previous.sender_id
            == latest.receiver_id

            and previous.receiver_id
            == latest.sender_id
        ):

            return MediationResult(
                action=(
                    MediationAction
                    .SUGGEST_COALITION
                ),

                reason=(
                    "Offer structure is not suitable "
                    "for a bilateral compromise."
                ),
            )

        proposal = (
            self._build_midpoint_proposal(
                previous,
                latest,
            )
        )

        if proposal is None:

            return MediationResult(
                action=(
                    MediationAction
                    .SUGGEST_COALITION
                ),

                reason=(
                    "No simple bilateral compromise "
                    "could be constructed."
                ),
            )

        return MediationResult(
            action=(
                MediationAction
                .SUGGEST_COUNTER
            ),

            reason=(
                "A midpoint compromise was generated "
                "using only publicly revealed offers."
            ),

            proposal=proposal,
        )

    # ========================================================
    # MIDPOINT PROPOSAL
    # ========================================================

    def _build_midpoint_proposal(
        self,
        previous,
        latest,
    ) -> MediationProposal | None:
        """
        Exemple :

        Alice :
            10 STORAGE
            contre 8 H100

        Bob :
            8 H100
            contre 15 STORAGE

        Médiateur :

            Alice propose 12.5 STORAGE
            contre 8 H100
        """

        next_sender = (
            latest.receiver_id
        )

        next_receiver = (
            latest.sender_id
        )

        # ----------------------------------------
        # WHAT NEXT SENDER GIVES
        #
        # previous.offered_resources
        # vs latest.requested_resources
        # ----------------------------------------

        offered_resources: list[
            Resource
        ] = []

        for previous_resource in (
            previous.offered_resources
        ):

            matching = next(
                (
                    item

                    for item
                    in latest.requested_resources

                    if (
                        item.resource_type
                        == previous_resource.resource_type

                        and item.unit
                        == previous_resource.unit
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

            offered_resources.append(
                Resource(
                    resource_type=(
                        previous_resource
                        .resource_type
                    ),

                    quantity=midpoint,

                    unit=(
                        previous_resource.unit
                    ),

                    attributes=dict(
                        previous_resource
                        .attributes
                    ),
                )
            )

        # ----------------------------------------
        # WHAT NEXT SENDER WANTS
        #
        # previous.requested_resources
        # vs latest.offered_resources
        # ----------------------------------------

        requested_resources: list[
            ResourceRequest
        ] = []

        for previous_request in (
            previous.requested_resources
        ):

            matching = next(
                (
                    item

                    for item
                    in latest.offered_resources

                    if (
                        item.resource_type
                        == previous_request.resource_type

                        and item.unit
                        == previous_request.unit
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

            requested_resources.append(
                ResourceRequest(
                    resource_type=(
                        previous_request
                        .resource_type
                    ),

                    quantity=midpoint,

                    unit=(
                        previous_request.unit
                    ),

                    deadline=(
                        previous_request.deadline
                    ),

                    attributes=dict(
                        previous_request
                        .attributes
                    ),
                )
            )

        if (
            not offered_resources
            or not requested_resources
        ):

            return None

        return MediationProposal(
            sender_id=next_sender,

            receiver_id=next_receiver,

            offered_resources=(
                offered_resources
            ),

            requested_resources=(
                requested_resources
            ),
        )