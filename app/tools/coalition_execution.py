# app/tools/coalition_execution.py

from __future__ import annotations

from collections import defaultdict
from typing import Mapping

from app.models.resource import Resource
from app.models.user import User
from app.tools.need_tools import satisfy_user_need
from app.tools.coalition_tools import (
    CoalitionProposal,
    evaluate_coalition_feasibility,
)


def _matching_resources(
    user: User,
    resource_type: str,
    unit: str,
) -> list[Resource]:
    return [
        resource
        for resource in user.resources
        if (
            resource.resource_type == resource_type
            and resource.unit == unit
        )
    ]


def _deduct(
    user: User,
    resource_type: str,
    unit: str,
    quantity: float,
) -> None:
    remaining = quantity

    for resource in list(
        _matching_resources(
            user,
            resource_type,
            unit,
        )
    ):
        if remaining <= 0:
            break

        take = min(
            remaining,
            resource.quantity,
        )

        if take == resource.quantity:
            user.resources.remove(resource)
        else:
            resource.quantity -= take

        remaining -= take

    if remaining > 1e-9:
        raise ValueError(
            "Coalition provider no longer owns enough resource."
        )


def _credit(
    user: User,
    resource_type: str,
    unit: str,
    quantity: float,
    *,
    attributes: dict | None = None,
) -> None:
    existing = next(
        (
            resource
            for resource in user.resources
            if (
                resource.resource_type == resource_type
                and resource.unit == unit
            )
        ),
        None,
    )

    if existing is not None:
        existing.quantity += quantity
        return

    user.resources.append(
        Resource(
            resource_type=resource_type,
            quantity=quantity,
            unit=unit,
            attributes=dict(attributes or {}),
        )
    )


def execute_coalition_atomically(
    proposal: CoalitionProposal,
    users: Mapping[str, User],
) -> bool:
    """
    Execute every coalition transfer as one logical transaction.

    Phase 1 validates the entire coalition against the CURRENT world.
    Phase 2 snapshots participant inventories and needs, applies every
    outgoing deduction, then every incoming credit. Any unexpected
    exception restores every participant snapshot before re-raising.

    This gives the in-memory hackathon world all-or-nothing behavior.
    """

    participants = [
        users[user_id]
        for user_id in proposal.participant_ids
        if user_id in users
    ]

    feasibility = evaluate_coalition_feasibility(
        proposal,
        participants,
    )

    if not feasibility.feasible:
        raise ValueError(
            "Coalition is no longer feasible."
        )

    resource_snapshots = {
        user.id: [
            resource.model_copy(deep=True)
            for resource in user.resources
        ]
        for user in participants
    }
    need_snapshots = {
        user.id: [
            need.model_copy(deep=True)
            for need in user.needs
        ]
        for user in participants
    }

    outgoing: dict[
        tuple[str, str, str],
        float,
    ] = defaultdict(float)

    incoming: dict[
        tuple[str, str, str],
        float,
    ] = defaultdict(float)

    source_attributes: dict[
        tuple[str, str, str],
        dict,
    ] = {}

    for transfer in proposal.transfers:
        if transfer.quantity <= 0:
            raise ValueError(
                "Coalition transfers must be positive."
            )

        provider = users.get(
            transfer.from_user_id
        )
        receiver = users.get(
            transfer.to_user_id
        )

        if provider is None or receiver is None:
            raise ValueError(
                "Coalition participant disappeared."
            )

        outgoing[
            (
                provider.id,
                transfer.resource_type,
                transfer.unit,
            )
        ] += transfer.quantity

        incoming[
            (
                receiver.id,
                transfer.resource_type,
                transfer.unit,
            )
        ] += transfer.quantity

        source = next(
            iter(
                _matching_resources(
                    provider,
                    transfer.resource_type,
                    transfer.unit,
                )
            ),
            None,
        )

        source_attributes.setdefault(
            (
                receiver.id,
                transfer.resource_type,
                transfer.unit,
            ),
            dict(
                source.attributes
                if source is not None
                else {}
            ),
        )

    try:
        # Deduct every provider first so incoming resources can never
        # be recycled to fund another transfer in the same coalition.
        for (
            user_id,
            resource_type,
            unit,
        ), quantity in outgoing.items():
            _deduct(
                users[user_id],
                resource_type,
                unit,
                quantity,
            )

        for (
            user_id,
            resource_type,
            unit,
        ), quantity in incoming.items():
            _credit(
                users[user_id],
                resource_type,
                unit,
                quantity,
                attributes=source_attributes.get(
                    (
                        user_id,
                        resource_type,
                        unit,
                    )
                ),
            )
            satisfy_user_need(
                users[user_id],
                resource_type=resource_type,
                unit=unit,
                quantity=quantity,
            )

    except Exception:
        for participant in participants:
            participant.resources = [
                resource.model_copy(deep=True)
                for resource in resource_snapshots[
                    participant.id
                ]
            ]
            participant.needs = [
                need.model_copy(deep=True)
                for need in need_snapshots[
                    participant.id
                ]
            ]
        raise

    return True
