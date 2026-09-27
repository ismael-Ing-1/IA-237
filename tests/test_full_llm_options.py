from app.agents.personal_agent import (
    NegotiationChoiceAction,
    PersonalAgent,
)
from app.models.resource import Resource, ResourceRequest
from app.models.user import User
from app.privacy import PrivacyGuard
from app.reputation import ReputationManager
from app.simulation import SimulationWorld
from app.tools.negotiation_tools import create_negotiation, send_offer


def _world():
    world = SimulationWorld()
    alice = User(
        id="alice",
        name="Alice",
        resources=[
            Resource(
                resource_type="STORAGE",
                quantity=40,
                unit="TB-day",
            )
        ],
        needs=[
            ResourceRequest(
                resource_type="H100",
                quantity=8,
                unit="gpu-hour",
            )
        ],
    )
    alice.constraints.max_quantity_to_give = {
        "STORAGE": 20
    }

    bob = User(
        id="bob",
        name="Bob",
        resources=[
            Resource(
                resource_type="H100",
                quantity=16,
                unit="gpu-hour",
            )
        ],
        needs=[
            ResourceRequest(
                resource_type="STORAGE",
                quantity=12,
                unit="TB-day",
            )
        ],
    )
    bob.constraints.max_quantity_to_give = {
        "H100": 10
    }

    world.add_user(alice)
    world.add_user(bob)

    rep = ReputationManager()
    rep.register_user("alice")
    rep.register_user("bob")

    return world, rep


def test_initial_offer_has_multiple_safe_public_choices():
    world, rep = _world()
    agent = PersonalAgent(
        "alice",
        world,
        rep,
        PrivacyGuard(),
    )

    options = agent.build_initial_offer_options(
        partner_id="bob",
        authorized_offered_resources=[
            Resource(
                resource_type="STORAGE",
                quantity=18,
                unit="TB-day",
            )
        ],
        requested_resources=[
            ResourceRequest(
                resource_type="H100",
                quantity=8,
                unit="gpu-hour",
            )
        ],
    )

    assert len(options) >= 3
    assert any(
        item.choice_id == "initial_direct"
        for item in options
    )
    assert len({
        item.offered_resources[0].quantity
        for item in options
    }) >= 2


def test_response_menu_contains_multiple_counter_amounts():
    world, rep = _world()
    alice = PersonalAgent(
        "alice",
        world,
        rep,
        PrivacyGuard(),
    )

    negotiation = create_negotiation(
        ["alice", "bob"],
        max_rounds=10,
    )
    world.add_negotiation(negotiation)

    offer = send_offer(
        negotiation=negotiation,
        sender_id="bob",
        receiver_id="alice",
        offered_resources=[
            Resource(
                resource_type="H100",
                quantity=8,
                unit="gpu-hour",
            )
        ],
        requested_resources=[
            ResourceRequest(
                resource_type="STORAGE",
                quantity=16,
                unit="TB-day",
            )
        ],
    )

    menu = alice.build_response_options(
        negotiation,
        offer,
    )

    counters = [
        item
        for item in menu.options
        if item.action
        == NegotiationChoiceAction.COUNTER
    ]

    assert len(counters) >= 2
    assert any(
        item.action
        == NegotiationChoiceAction.ACCEPT
        for item in menu.options
    )
    assert any(
        item.action
        == NegotiationChoiceAction.REJECT
        for item in menu.options
    )
