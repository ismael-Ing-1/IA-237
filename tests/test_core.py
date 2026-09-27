# tests/test_core.py

import pytest

from app.models import (
    User,
    UserConstraints,
    Resource,
    ResourceRequest,
    OfferStatus,
    NegotiationStatus,
)

from app.market.registry import MarketRegistry
from app.market.exchange import execute_exchange

from app.tools.market_tools import (
    search_providers,
    search_requesters,
    get_public_profile,
)

from app.tools.negotiation_tools import (
    create_negotiation,
    send_offer,
    counter_offer,
    accept_offer,
    request_human_approval,
    approve_negotiation,
)

from app.tools.privacy_tools import (
    can_user_give,
    evaluate_offer_against_private_constraints,
    get_negotiation_margin,
    MarginLevel,
)

from app.tools.coalition_tools import (
    build_exchange_graph,
    find_exchange_cycles,
    find_possible_coalitions,
)


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def alice():
    """
    Alice possède du STORAGE
    et recherche du H100.
    """

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
                "STORAGE": 20
            }
        ),
    )


@pytest.fixture
def bob():
    """
    Bob possède du H100
    et recherche du A100.
    """

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
                resource_type="A100",
                quantity=5,
                unit="gpu-hour",
            )
        ],
    )


@pytest.fixture
def charlie():
    """
    Charlie possède du A100
    et recherche du STORAGE.

    Cela crée le cycle :

        Alice -> Charlie
        Charlie -> Bob
        Bob -> Alice
    """

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
def registry(alice, bob, charlie):
    registry = MarketRegistry()

    registry.register_user(alice)
    registry.register_user(bob)
    registry.register_user(charlie)

    return registry


# ============================================================
# MODELS
# ============================================================


def test_resource_model():
    resource = Resource(
        resource_type="H100",
        quantity=10,
        unit="gpu-hour",
    )

    assert resource.resource_type == "H100"
    assert resource.quantity == 10
    assert resource.unit == "gpu-hour"
    assert resource.id is not None


def test_resource_quantity_must_be_positive():
    with pytest.raises(ValueError):

        Resource(
            resource_type="H100",
            quantity=-10,
            unit="gpu-hour",
        )


def test_user_public_profile_hides_private_data(alice):
    profile = alice.to_public_profile()

    assert profile.user_id == alice.id

    assert "STORAGE" in profile.offered_resource_types
    assert "H100" in profile.requested_resource_types

    # Le profil public ne doit pas exposer
    # les contraintes privées.
    assert not hasattr(
        profile,
        "constraints",
    )

    assert not hasattr(
        profile,
        "preferred_partners",
    )


def test_user_resource_quantity(alice):
    quantity = alice.get_resource_quantity(
        "STORAGE"
    )

    assert quantity == 50


# ============================================================
# MARKET REGISTRY
# ============================================================


def test_registry_get_public_profile(
    registry,
    alice,
):
    profile = registry.get_public_profile(
        alice.id
    )

    assert profile is not None
    assert profile.user_id == alice.id
    assert profile.display_name == "Alice"


def test_registry_find_h100_provider(
    registry,
    bob,
):
    providers = registry.find_providers(
        "H100"
    )

    ids = [
        provider.user_id
        for provider in providers
    ]

    assert bob.id in ids


def test_registry_find_storage_requester(
    registry,
    charlie,
):
    requesters = registry.find_requesters(
        "STORAGE"
    )

    ids = [
        requester.user_id
        for requester in requesters
    ]

    assert charlie.id in ids


# ============================================================
# MARKET TOOLS
# ============================================================


def test_search_providers_tool(
    registry,
    alice,
    bob,
):
    providers = search_providers(
        registry=registry,
        resource_type="H100",
        requester_id=alice.id,
    )

    ids = [
        provider.user_id
        for provider in providers
    ]

    assert bob.id in ids

    # Alice ne doit jamais se retrouver elle-même
    assert alice.id not in ids


def test_search_requesters_tool(
    registry,
    bob,
    charlie,
):
    requesters = search_requesters(
        registry=registry,
        resource_type="STORAGE",
        provider_id=bob.id,
    )

    ids = [
        requester.user_id
        for requester in requesters
    ]

    assert charlie.id in ids


def test_market_tool_public_profile(
    registry,
    alice,
):
    profile = get_public_profile(
        registry,
        alice.id,
    )

    assert profile is not None
    assert profile.display_name == "Alice"


# ============================================================
# NEGOTIATION TOOLS
# ============================================================


def test_complete_negotiation(
    alice,
    bob,
):
    negotiation = create_negotiation(
        participant_ids=[
            alice.id,
            bob.id,
        ]
    )

    assert (
        negotiation.status
        == NegotiationStatus.OPEN
    )

    # Alice propose :
    # 10 STORAGE contre 8 H100.

    first_offer = send_offer(
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

    assert len(negotiation.offers) == 1

    assert (
        negotiation.status
        == NegotiationStatus.NEGOTIATING
    )

    # Bob demande 15 STORAGE.

    second_offer = counter_offer(
        negotiation=negotiation,

        previous_offer_id=first_offer.id,

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

    assert (
        first_offer.status
        == OfferStatus.COUNTERED
    )

    assert len(negotiation.offers) == 2

    # Alice accepte.

    accepted_offer = accept_offer(
        negotiation,
        second_offer.id,
    )

    assert (
        accepted_offer.status
        == OfferStatus.ACCEPTED
    )

    assert (
        negotiation.status
        == NegotiationStatus.AGREEMENT_FOUND
    )

    # Human in the loop

    request_human_approval(
        negotiation
    )

    assert (
        negotiation.status
        == NegotiationStatus.WAITING_HUMAN
    )

    approve_negotiation(
        negotiation
    )

    assert (
        negotiation.status
        == NegotiationStatus.APPROVED
    )


# ============================================================
# PRIVACY TOOLS
# ============================================================


def test_private_resource_limit(alice):
    # Alice possède 50 STORAGE,
    # mais refuse d'en donner plus de 20.

    assert can_user_give(
        alice,
        "STORAGE",
        10,
    )

    assert can_user_give(
        alice,
        "STORAGE",
        20,
    )

    assert not can_user_give(
        alice,
        "STORAGE",
        21,
    )


def test_negotiation_margin(alice):
    assert (
        get_negotiation_margin(
            alice,
            "STORAGE",
            5,
        )
        == MarginLevel.HIGH
    )

    assert (
        get_negotiation_margin(
            alice,
            "STORAGE",
            19,
        )
        == MarginLevel.LOW
    )

    assert (
        get_negotiation_margin(
            alice,
            "STORAGE",
            30,
        )
        == MarginLevel.NONE
    )


def test_offer_privacy_validation(
    alice,
    bob,
):
    negotiation = create_negotiation(
        [
            alice.id,
            bob.id,
        ]
    )

    offer = send_offer(
        negotiation=negotiation,

        sender_id=alice.id,
        receiver_id=bob.id,

        offered_resources=[
            Resource(
                resource_type="STORAGE",
                quantity=15,
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

    decision = (
        evaluate_offer_against_private_constraints(
            alice,
            offer,
        )
    )

    assert decision.allowed is True


# ============================================================
# COALITIONS
# ============================================================


def test_exchange_graph(
    alice,
    bob,
    charlie,
):
    users = [
        alice,
        bob,
        charlie,
    ]

    graph = build_exchange_graph(
        users
    )

    # Alice possède STORAGE
    # dont Charlie a besoin.
    assert graph.has_edge(
        alice.id,
        charlie.id,
    )

    # Charlie possède A100
    # dont Bob a besoin.
    assert graph.has_edge(
        charlie.id,
        bob.id,
    )

    # Bob possède H100
    # dont Alice a besoin.
    assert graph.has_edge(
        bob.id,
        alice.id,
    )


def test_find_three_user_cycle(
    alice,
    bob,
    charlie,
):
    users = [
        alice,
        bob,
        charlie,
    ]

    cycles = find_exchange_cycles(
        users=users,
        min_size=3,
        max_size=3,
        target_user_id=alice.id,
    )

    assert len(cycles) >= 1

    expected_users = {
        alice.id,
        bob.id,
        charlie.id,
    }

    assert any(
        set(cycle) == expected_users
        for cycle in cycles
    )


def test_find_valid_coalition(
    alice,
    bob,
    charlie,
):
    users = [
        alice,
        bob,
        charlie,
    ]

    proposals = find_possible_coalitions(
        users=users,
        target_user_id=alice.id,
        min_size=3,
        max_size=3,
    )

    assert len(proposals) >= 1

    proposal = proposals[0]

    assert set(
        proposal.participant_ids
    ) == {
        alice.id,
        bob.id,
        charlie.id,
    }

    assert len(proposal.transfers) == 3


# ============================================================
# MARKET EXCHANGE
# ============================================================


def test_execute_bilateral_exchange(
    alice,
    bob,
):
    """
    Teste le workflow complet :

    Offer
      ↓
    Negotiation
      ↓
    Approval
      ↓
    Exchange
      ↓
    Inventories updated
    """

    negotiation = create_negotiation(
        [
            alice.id,
            bob.id,
        ]
    )

    # Alice propose 15 STORAGE
    # contre 8 H100.

    offer = send_offer(
        negotiation=negotiation,

        sender_id=alice.id,
        receiver_id=bob.id,

        offered_resources=[
            Resource(
                resource_type="STORAGE",
                quantity=15,
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

    accept_offer(
        negotiation,
        offer.id,
    )

    request_human_approval(
        negotiation
    )

    approve_negotiation(
        negotiation
    )

    users = {
        alice.id: alice,
        bob.id: bob,
    }

    alice_storage_before = (
        alice.get_resource_quantity(
            "STORAGE"
        )
    )

    alice_h100_before = (
        alice.get_resource_quantity(
            "H100"
        )
    )

    bob_storage_before = (
        bob.get_resource_quantity(
            "STORAGE"
        )
    )

    bob_h100_before = (
        bob.get_resource_quantity(
            "H100"
        )
    )

    result = execute_exchange(
        negotiation,
        users,
    )

    assert result is True

    # Alice a donné 15 STORAGE.

    assert (
        alice.get_resource_quantity(
            "STORAGE"
        )
        == alice_storage_before - 15
    )

    # Alice a reçu 8 H100.

    assert (
        alice.get_resource_quantity(
            "H100"
        )
        == alice_h100_before + 8
    )

    # Bob a reçu 15 STORAGE.

    assert (
        bob.get_resource_quantity(
            "STORAGE"
        )
        == bob_storage_before + 15
    )

    # Bob a donné 8 H100.

    assert (
        bob.get_resource_quantity(
            "H100"
        )
        == bob_h100_before - 8
    )