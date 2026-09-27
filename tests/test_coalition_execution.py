from __future__ import annotations

import pytest

from app.models.resource import Resource, ResourceRequest
from app.models.user import User
from app.tools.coalition_execution import execute_coalition_atomically
from app.tools.coalition_tools import CoalitionProposal, CoalitionTransfer


def _world():
    alice = User(
        id="alice",
        name="Alice",
        resources=[Resource(resource_type="STORAGE", quantity=40, unit="TB-day")],
        needs=[ResourceRequest(resource_type="H100", quantity=8, unit="gpu-hour")],
    )
    bob = User(
        id="bob",
        name="Bob",
        resources=[Resource(resource_type="H100", quantity=16, unit="gpu-hour")],
        needs=[ResourceRequest(resource_type="A100", quantity=5, unit="gpu-hour")],
    )
    charlie = User(
        id="charlie",
        name="Charlie",
        resources=[Resource(resource_type="A100", quantity=10, unit="gpu-hour")],
        needs=[ResourceRequest(resource_type="STORAGE", quantity=10, unit="TB-day")],
    )
    users = {user.id: user for user in (alice, bob, charlie)}
    proposal = CoalitionProposal(
        participant_ids=["alice", "charlie", "bob"],
        transfers=[
            CoalitionTransfer(from_user_id="alice", to_user_id="charlie", resource_type="STORAGE", quantity=10, unit="TB-day"),
            CoalitionTransfer(from_user_id="charlie", to_user_id="bob", resource_type="A100", quantity=5, unit="gpu-hour"),
            CoalitionTransfer(from_user_id="bob", to_user_id="alice", resource_type="H100", quantity=8, unit="gpu-hour"),
        ],
    )
    return users, proposal


def _quantity(user: User, resource_type: str, unit: str) -> float:
    return sum(
        item.quantity
        for item in user.resources
        if item.resource_type == resource_type and item.unit == unit
    )


def test_atomic_coalition_commits_every_transfer():
    users, proposal = _world()

    assert execute_coalition_atomically(proposal, users) is True

    assert _quantity(users["alice"], "STORAGE", "TB-day") == 30
    assert _quantity(users["alice"], "H100", "gpu-hour") == 8
    assert _quantity(users["bob"], "H100", "gpu-hour") == 8
    assert _quantity(users["bob"], "A100", "gpu-hour") == 5
    assert _quantity(users["charlie"], "A100", "gpu-hour") == 5
    assert _quantity(users["charlie"], "STORAGE", "TB-day") == 10

    assert not users["alice"].needs
    assert not users["bob"].needs
    assert not users["charlie"].needs


def test_atomic_coalition_rolls_back_on_unexpected_failure(monkeypatch):
    users, proposal = _world()
    before = {
        user_id: [item.model_copy(deep=True) for item in user.resources]
        for user_id, user in users.items()
    }

    import app.tools.coalition_execution as engine

    original_credit = engine._credit
    calls = 0

    def failing_credit(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("synthetic settlement failure")
        return original_credit(*args, **kwargs)

    monkeypatch.setattr(engine, "_credit", failing_credit)

    with pytest.raises(RuntimeError, match="synthetic settlement failure"):
        execute_coalition_atomically(proposal, users)

    for user_id, resources in before.items():
        assert users[user_id].resources == resources
