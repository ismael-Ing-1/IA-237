# app/tools/need_tools.py

from __future__ import annotations

from app.models.resource import ResourceRequest
from app.models.user import User


def sync_user_need(
    user: User,
    request: ResourceRequest,
) -> ResourceRequest:
    """
    Make the submitted objective the authoritative remaining need.

    Priority:
    1. same need id;
    2. same resource type + unit;
    3. otherwise append a new need.

    This lets the GoalComposer edit an existing need without creating
    duplicates every time the quantity changes.
    """

    replacement = request.model_copy(deep=True)

    index = next(
        (
            i
            for i, need in enumerate(user.needs)
            if need.id == request.id
        ),
        None,
    )

    if index is None:
        index = next(
            (
                i
                for i, need in enumerate(user.needs)
                if (
                    need.resource_type == request.resource_type
                    and need.unit == request.unit
                )
            ),
            None,
        )

    if index is None:
        user.needs.append(replacement)
    else:
        # Preserve the stable existing identifier if the frontend supplied
        # a fresh id but edited an existing resource need.
        existing = user.needs[index]
        replacement = replacement.model_copy(
            update={"id": existing.id},
        )
        user.needs[index] = replacement

    return replacement


def satisfy_user_need(
    user: User,
    *,
    resource_type: str,
    unit: str,
    quantity: float,
) -> float:
    """
    Reduce remaining demand after resources were ACTUALLY transferred.

    Fully satisfied needs are removed from user.needs because ResourceRequest
    quantities are strictly positive. The returned value is the amount that
    was applied to outstanding demand.
    """

    if quantity <= 0:
        return 0.0

    remaining = quantity
    applied = 0.0

    for need in list(user.needs):
        if remaining <= 1e-9:
            break

        if (
            need.resource_type != resource_type
            or need.unit != unit
        ):
            continue

        used = min(need.quantity, remaining)
        applied += used
        remaining -= used

        if used >= need.quantity - 1e-9:
            user.needs.remove(need)
        else:
            index = user.needs.index(need)
            user.needs[index] = need.model_copy(
                deep=True,
                update={
                    "quantity": round(
                        need.quantity - used,
                        9,
                    )
                },
            )

    return applied
