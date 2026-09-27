# tests/test_agents.py

import pytest

from app.agents import (
    AgentAction,
    CoalitionAgent,
    MediationAction,
    MediatorAgent,
    PersonalAgent,
)

from app.models import (
    OfferStatus,
    Resource,
    ResourceRequest,
    User,
    UserConstraints,
)

from app.privacy import (
    PrivacyGuard,
)

from app.reputation import (
    ReputationManager,
)

from app.simulation import (
    SimulationWorld,
)

from app.tools.negotiation_tools import (
    counter_offer,
    create_negotiation,
    send_offer,
)


# ============================================================
# USERS
# ============================================================


@pytest.fixture
def alice():
    return User(
        name="Alice",

        resources=[
            Resource(
                resource_type="STORAGE",
                quantity=50,
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

        constraints=UserConstraints(
            max_quantity_to_give={
                "STORAGE": 20,
            }
        ),
    )


@pytest.fixture
def bob():
    return User(
        name="Bob",

        resources=[
            Resource(
                resource_type="H100",
                quantity=20,
                unit="gpu-hour",
            )
        ],

        needs=[
            ResourceRequest(
                resource_type="STORAGE",
                quantity=10,
                unit="TB-day",
            )
        ],

        constraints=UserConstraints(
            max_quantity_to_give={
                "H100": 10,
            }
        ),
    )


@pytest.fixture
def charlie():
    return User(
        name="Charlie",

        resources=[
            Resource(
                resource_type="A100",
                quantity=10,
                unit="gpu-hour",
            )
        ],

        needs=[
            ResourceRequest(
                resource_type="STORAGE",
                quantity=10,
                unit="TB-day",
            )
        ],
    )


@pytest.fixture
def coalition_bob():
    """
    Bob utilisé pour le scénario :

        Alice -> Charlie
        Charlie -> Bob
        Bob -> Alice
    """

    return User(
        name="Coalition Bob",

        resources=[
            Resource(
                resource_type="H100",
                quantity=20,
                unit="gpu-hour",
            )
        ],

        needs=[
            ResourceRequest(
                resource_type="A100",
                quantity=5,
                unit="gpu-hour",
            )
        ],
    )


@pytest.fixture
def reputation():
    return ReputationManager()


@pytest.fixture
def privacy():
    return PrivacyGuard()


@pytest.fixture
def world(
    alice,
    bob,
):
    world = SimulationWorld()

    world.add_user(
        alice
    )

    world.add_user(
        bob
    )

    return world


# ============================================================
# PERSONAL AGENT
# ============================================================


def test_personal_agent_discovers_provider(
    world,
    alice,
    bob,
    reputation,
    privacy,
):
    agent = PersonalAgent(
        user_id=alice.id,

        world=world,

        reputation=reputation,

        privacy_guard=privacy,
    )

    candidates = (
        agent.discover_candidates(
            "H100"
        )
    )

    assert len(candidates) == 1

    assert (
        candidates[0].user_id
        == bob.id
    )


def test_preferred_partner_has_priority(
    alice,
    bob,
    reputation,
    privacy,
):
    david = User(
        name="David",

        resources=[
            Resource(
                resource_type="H100",
                quantity=20,
                unit="gpu-hour",
            )
        ],
    )

    world = SimulationWorld()

    world.add_user(alice)
    world.add_user(bob)
    world.add_user(david)

    # David a meilleure réputation.
    reputation.record_success(
        david.id
    )

    # Mais Alice préfère explicitement Bob.
    alice.preferred_partners = [
        bob.id
    ]

    agent = PersonalAgent(
        user_id=alice.id,

        world=world,

        reputation=reputation,

        privacy_guard=privacy,
    )

    candidates = (
        agent.discover_candidates(
            "H100"
        )
    )

    assert (
        candidates[0].user_id
        == bob.id
    )


def test_personal_agent_starts_negotiation(
    world,
    alice,
    bob,
    reputation,
    privacy,
):
    agent = PersonalAgent(
        user_id=alice.id,

        world=world,

        reputation=reputation,

        privacy_guard=privacy,
    )

    result = agent.pursue_request(
        request=alice.needs[0],

        offered_resources=[
            Resource(
                resource_type="STORAGE",
                quantity=10,
                unit="TB-day",
            )
        ],
    )

    assert (
        result.decision.action
        == AgentAction.START_NEGOTIATION
    )

    assert (
        result.decision.partner_id
        == bob.id
    )

    assert result.negotiation is not None

    assert result.offer is not None


def test_outgoing_private_limit_is_enforced(
    world,
    alice,
    bob,
    reputation,
    privacy,
):
    agent = PersonalAgent(
        user_id=alice.id,

        world=world,

        reputation=reputation,

        privacy_guard=privacy,
    )

    # Alice limite STORAGE à 20.
    with pytest.raises(ValueError):

        agent.start_negotiation(
            partner_id=bob.id,

            offered_resources=[
                Resource(
                    resource_type="STORAGE",
                    quantity=30,
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


def test_message_is_sanitized_before_sending(
    world,
    alice,
    bob,
    reputation,
    privacy,
):
    agent = PersonalAgent(
        user_id=alice.id,

        world=world,

        reputation=reputation,

        privacy_guard=privacy,
    )

    result = agent.start_negotiation(
        partner_id=bob.id,

        offered_resources=[
            Resource(
                resource_type="STORAGE",
                quantity=10,
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

        message=(
            "I own 50 STORAGE and my "
            "maximum STORAGE offer is 20."
        ),
    )

    assert "[PRIVATE]" in (
        result.offer.message
    )

    assert "50 STORAGE" not in (
        result.offer.message
    )


# ============================================================
# ACCEPT OFFER
# ============================================================


def test_receiver_accepts_valid_offer(
    world,
    alice,
    bob,
    reputation,
    privacy,
):
    negotiation = create_negotiation(
        [
            alice.id,
            bob.id,
        ]
    )

    world.add_negotiation(
        negotiation
    )

    offer = send_offer(
        negotiation=negotiation,

        sender_id=alice.id,

        receiver_id=bob.id,

        offered_resources=[
            Resource(
                resource_type="STORAGE",
                quantity=10,
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

    bob_agent = PersonalAgent(
        user_id=bob.id,

        world=world,

        reputation=reputation,

        privacy_guard=privacy,
    )

    result = bob_agent.handle_offer(
        negotiation,
        offer,
    )

    assert (
        result.decision.action
        == AgentAction.ACCEPT
    )

    assert (
        offer.status
        == OfferStatus.ACCEPTED
    )


# ============================================================
# COUNTER OFFER
# ============================================================


def test_receiver_generates_safe_counter_offer(
    alice,
    reputation,
    privacy,
):
    bob = User(
        name="Bob",

        resources=[
            Resource(
                resource_type="H100",
                quantity=20,
                unit="gpu-hour",
            )
        ],

        needs=[
            ResourceRequest(
                resource_type="STORAGE",
                quantity=10,
                unit="TB-day",
            )
        ],

        constraints=UserConstraints(
            max_quantity_to_give={
                "H100": 5,
            }
        ),
    )

    world = SimulationWorld()

    world.add_user(alice)
    world.add_user(bob)

    negotiation = create_negotiation(
        [
            alice.id,
            bob.id,
        ]
    )

    world.add_negotiation(
        negotiation
    )

    offer = send_offer(
        negotiation=negotiation,

        sender_id=alice.id,

        receiver_id=bob.id,

        offered_resources=[
            Resource(
                resource_type="STORAGE",
                quantity=10,
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

    bob_agent = PersonalAgent(
        user_id=bob.id,

        world=world,

        reputation=reputation,

        privacy_guard=privacy,
    )

    result = bob_agent.handle_offer(
        negotiation,
        offer,
    )

    assert (
        result.decision.action
        == AgentAction.COUNTER
    )

    assert (
        result.offer.offered_resources[0]
        .quantity
        == 5
    )

    assert (
        result.offer.sender_id
        == bob.id
    )


# ============================================================
# HUMAN VALIDATION
# ============================================================


def test_agent_requests_human_approval(
    world,
    alice,
    bob,
    reputation,
    privacy,
):
    negotiation = create_negotiation(
        [
            alice.id,
            bob.id,
        ]
    )

    world.add_negotiation(
        negotiation
    )

    offer = send_offer(
        negotiation=negotiation,

        sender_id=alice.id,

        receiver_id=bob.id,

        offered_resources=[
            Resource(
                resource_type="STORAGE",
                quantity=10,
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

    bob_agent = PersonalAgent(
        user_id=bob.id,

        world=world,

        reputation=reputation,

        privacy_guard=privacy,
    )

    bob_agent.handle_offer(
        negotiation,
        offer,
    )

    decision = (
        bob_agent
        .request_human_validation(
            negotiation
        )
    )

    assert (
        decision.action
        == AgentAction.WAIT_HUMAN
    )


# ============================================================
# MEDIATOR
# ============================================================


def test_mediator_builds_compromise(
    alice,
    bob,
):
    negotiation = create_negotiation(
        [
            alice.id,
            bob.id,
        ]
    )

    first = send_offer(
        negotiation=negotiation,

        sender_id=alice.id,

        receiver_id=bob.id,

        offered_resources=[
            Resource(
                resource_type="STORAGE",
                quantity=10,
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

    second = counter_offer(
        negotiation=negotiation,

        previous_offer_id=first.id,

        sender_id=bob.id,

        receiver_id=alice.id,

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
                quantity=15,
                unit="TB-day",
            )
        ],
    )

    assert second is not None

    mediator = MediatorAgent()

    result = mediator.mediate(
        negotiation
    )

    assert (
        result.action
        == MediationAction.SUGGEST_COUNTER
    )

    assert result.proposal is not None

    # Midpoint : (10 + 15) / 2
    assert (
        result.proposal
        .offered_resources[0]
        .quantity
        == 12.5
    )

    # Le médiateur n'a rien ajouté
    # à la négociation.
    assert len(
        negotiation.offers
    ) == 2


# ============================================================
# COALITION AGENT
# ============================================================


def test_coalition_agent_finds_three_party_cycle(
    alice,
    charlie,
    coalition_bob,
    reputation,
):
    """
    Cycle :

        Alice -> Charlie : STORAGE

        Charlie -> Bob : A100

        Bob -> Alice : H100
    """

    world = SimulationWorld()

    world.add_user(
        alice
    )

    world.add_user(
        charlie
    )

    world.add_user(
        coalition_bob
    )

    agent = CoalitionAgent(
        world=world,

        reputation=reputation,
    )

    coalitions = agent.discover(
        target_user_id=alice.id,

        min_size=3,

        max_size=3,
    )

    assert len(coalitions) >= 1

    participants = set(
        coalitions[0]
        .proposal
        .participant_ids
    )

    assert participants == {
        alice.id,
        charlie.id,
        coalition_bob.id,
    }


def test_coalition_agent_does_not_execute_trade(
    alice,
    charlie,
    coalition_bob,
    reputation,
):
    world = SimulationWorld()

    world.add_user(alice)
    world.add_user(charlie)
    world.add_user(coalition_bob)

    alice_storage_before = (
        alice.get_resource_quantity(
            "STORAGE"
        )
    )

    bob_h100_before = (
        coalition_bob
        .get_resource_quantity(
            "H100"
        )
    )

    agent = CoalitionAgent(
        world,
        reputation,
    )

    result = agent.recommend(
        alice.id
    )

    assert result is not None

    # Simple proposition :
    # aucune ressource n'est transférée.
    assert (
        alice.get_resource_quantity(
            "STORAGE"
        )
        == alice_storage_before
    )

    assert (
        coalition_bob
        .get_resource_quantity(
            "H100"
        )
        == bob_h100_before
    )