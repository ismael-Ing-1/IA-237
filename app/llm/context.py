from __future__ import annotations

from typing import Any

from app.agents.coalition_agent import RankedCoalition
from app.agents.personal_agent import CandidatePartner
from app.models.negotiation import Negotiation


def _resource_line(item: Any) -> dict:
    return {
        "resource_type": item.resource_type,
        "quantity": item.quantity,
        "unit": item.unit,
    }


def public_candidate_context(
    *,
    strategy: str,
    requested_resource_type: str,
    candidates: list[CandidatePartner],
) -> dict:
    """
    Candidate context deliberately excludes:
    - exact inventories;
    - blocked/preferred partner lists;
    - private limits;
    - private budgets.
    """

    return {
        "strategy": strategy,
        "requested_resource_type": requested_resource_type,
        "candidates": [
            {
                "user_id": item.user_id,
                "display_name": item.display_name,
                "reputation": item.reputation,
                "offered_resource_types": (
                    item.offered_resource_types
                ),
                "requested_resource_types": (
                    item.requested_resource_types
                ),
            }
            for item in candidates
        ],
    }


def public_negotiation_context(
    *,
    negotiation: Negotiation,
    receiver_strategy: str,
) -> dict:
    """
    Offer messages are omitted to avoid prompt-injection via free text.
    Only public structural terms are sent.
    """

    return {
        "receiver_strategy": receiver_strategy,
        "current_round": negotiation.current_round,
        "offers": [
            {
                "sender_id": offer.sender_id,
                "receiver_id": offer.receiver_id,
                "offered_resources": [
                    _resource_line(item)
                    for item in offer.offered_resources
                ],
                "requested_resources": [
                    _resource_line(item)
                    for item in offer.requested_resources
                ],
            }
            for offer in negotiation.offers
        ],
    }


def public_mediation_context(
    negotiation: Negotiation,
) -> dict:
    return {
        "participant_ids": list(
            negotiation.participant_ids
        ),
        "offers": [
            {
                "sender_id": offer.sender_id,
                "receiver_id": offer.receiver_id,
                "offered_resources": [
                    _resource_line(item)
                    for item in offer.offered_resources
                ],
                "requested_resources": [
                    _resource_line(item)
                    for item in offer.requested_resources
                ],
            }
            for offer in negotiation.offers
        ],
    }


def public_coalition_context(
    candidates: list[RankedCoalition],
) -> dict:
    return {
        "coalitions": [
            {
                "coalition_id": item.proposal.id,
                "participant_ids": list(
                    item.proposal.participant_ids
                ),
                "participant_count": (
                    item.participant_count
                ),
                "average_reputation": (
                    item.average_reputation
                ),
                "deterministic_score": item.score,
                "transfers": [
                    {
                        "from_user_id": (
                            transfer.from_user_id
                        ),
                        "to_user_id": (
                            transfer.to_user_id
                        ),
                        "resource_type": (
                            transfer.resource_type
                        ),
                        "quantity": transfer.quantity,
                        "unit": transfer.unit,
                    }
                    for transfer
                    in item.proposal.transfers
                ],
            }
            for item in candidates
        ]
    }
