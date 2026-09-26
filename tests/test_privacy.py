# tests/test_privacy_guard.py

import pytest

from app.models import (
    Offer,
    Resource,
    ResourceRequest,
    User,
    UserConstraints,
)

from app.privacy import (
    PrivacyAction,
    PrivacyGuard,
    PrivacyViolationType,
)


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def guard():
    return PrivacyGuard()


@pytest.fixture
def alice():
    return User(
        name="Alice",

        resources=[
            Resource(
                resource_type="STORAGE",
                quantity=50,
                unit="TB-day",
            ),

            Resource(
                resource_type="A100",
                quantity=10,
                unit="gpu-hour",
            ),
        ],

        needs=[
            ResourceRequest(
                resource_type="H100",
                quantity=8,
                unit="gpu-hour",
            )
        ],

        preferred_partners=[
            "bob-id",
            "charlie-id",
        ],

        blocked_partners=[
            "bad-provider-id",
        ],

        constraints=UserConstraints(

            max_quantity_to_give={
                "STORAGE": 20,
                "A100": 5,
            },

            reveal_exact_inventory=False,

            additional_constraints={
                "maximum_budget": 300,
                "internal_priority": "critical",
            },
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
    )


# ============================================================
# SAFE MESSAGE
# ============================================================


def test_safe_message_is_allowed(
    guard,
    alice,
):
    message = (
        "I am interested in acquiring H100 compute "
        "and can offer STORAGE."
    )

    result = guard.check_message(
        alice,
        message,
    )

    assert (
        result.action
        == PrivacyAction.ALLOW
    )

    assert result.safe is True

    assert (
        result.sanitized_message
        == message
    )

    assert len(
        result.violations
    ) == 0


# ============================================================
# PRIVATE LIMIT
# ============================================================


def test_private_limit_is_sanitized(
    guard,
    alice,
):
    message = (
        "My maximum STORAGE offer is 20."
    )

    result = guard.check_message(
        alice,
        message,
    )

    assert (
        result.action
        == PrivacyAction.SANITIZE
    )

    assert result.safe is True

    assert "[PRIVATE]" in (
        result.sanitized_message
    )

    assert any(
        violation.violation_type
        == PrivacyViolationType.PRIVATE_LIMIT

        for violation
        in result.violations
    )


def test_private_a100_limit_is_sanitized(
    guard,
    alice,
):
    message = (
        "I cannot go above 5 A100."
    )

    result = guard.check_message(
        alice,
        message,
    )

    assert (
        result.action
        == PrivacyAction.SANITIZE
    )

    assert "[PRIVATE]" in (
        result.sanitized_message
    )


# ============================================================
# EXACT INVENTORY
# ============================================================


def test_exact_inventory_is_sanitized(
    guard,
    alice,
):
    message = (
        "I currently own exactly "
        "50 STORAGE."
    )

    result = guard.check_message(
        alice,
        message,
    )

    assert (
        result.action
        == PrivacyAction.SANITIZE
    )

    assert "[PRIVATE]" in (
        result.sanitized_message
    )

    assert any(
        violation.violation_type
        == PrivacyViolationType.EXACT_INVENTORY

        for violation
        in result.violations
    )


def test_inventory_can_be_revealed_when_allowed(
    guard,
    alice,
):
    alice.constraints.reveal_exact_inventory = True

    message = (
        "I currently own 50 STORAGE."
    )

    result = guard.check_message(
        alice,
        message,
    )

    # Attention :
    # 20 est la limite privée,
    # mais 50 n'est plus protégée comme inventaire.
    assert (
        result.action
        == PrivacyAction.ALLOW
    )

    assert result.safe is True


# ============================================================
# PREFERRED PARTNERS
# ============================================================


def test_preferred_partner_is_hidden(
    guard,
    alice,
):
    message = (
        "My preferred partner is bob-id."
    )

    result = guard.check_message(
        alice,
        message,
    )

    assert (
        result.action
        == PrivacyAction.SANITIZE
    )

    assert (
        "bob-id"
        not in result.sanitized_message
    )

    assert "[PRIVATE]" in (
        result.sanitized_message
    )

    assert any(
        violation.violation_type
        == PrivacyViolationType.PREFERRED_PARTNERS

        for violation
        in result.violations
    )


# ============================================================
# BLOCKED PARTNERS
# ============================================================


def test_blocked_partner_is_hidden(
    guard,
    alice,
):
    message = (
        "I have blocked bad-provider-id."
    )

    result = guard.check_message(
        alice,
        message,
    )

    assert (
        result.action
        == PrivacyAction.SANITIZE
    )

    assert (
        "bad-provider-id"
        not in result.sanitized_message
    )

    assert any(
        violation.violation_type
        == PrivacyViolationType.BLOCKED_PARTNERS

        for violation
        in result.violations
    )


# ============================================================
# ADDITIONAL CONSTRAINTS
# ============================================================


def test_private_budget_is_hidden(
    guard,
    alice,
):
    message = (
        "My internal maximum budget is 300."
    )

    result = guard.check_message(
        alice,
        message,
    )

    assert (
        result.action
        == PrivacyAction.SANITIZE
    )

    assert (
        "300"
        not in result.sanitized_message
    )

    assert any(
        violation.violation_type
        == PrivacyViolationType.PRIVATE_CONSTRAINT

        for violation
        in result.violations
    )


def test_private_string_constraint_is_hidden(
    guard,
    alice,
):
    message = (
        "The internal priority is critical."
    )

    result = guard.check_message(
        alice,
        message,
    )

    assert (
        result.action
        == PrivacyAction.SANITIZE
    )

    assert (
        "critical"
        not in result.sanitized_message.lower()
    )


# ============================================================
# MULTIPLE LEAKS
# ============================================================


def test_multiple_private_values_are_sanitized(
    guard,
    alice,
):
    message = (
        "I own 50 STORAGE, "
        "my maximum STORAGE offer is 20, "
        "and bob-id is my preferred partner."
    )

    result = guard.check_message(
        alice,
        message,
    )

    assert (
        result.action
        == PrivacyAction.SANITIZE
    )

    assert len(
        result.violations
    ) >= 2

    assert (
        "bob-id"
        not in result.sanitized_message
    )

    assert "[PRIVATE]" in (
        result.sanitized_message
    )


# ============================================================
# SANITIZE HELPER
# ============================================================


def test_sanitize_message_helper(
    guard,
    alice,
):
    safe_message = guard.sanitize_message(
        alice,
        "I own 50 STORAGE.",
    )

    assert "[PRIVATE]" in (
        safe_message
    )


# ============================================================
# SAFE OFFER
# ============================================================


def test_safe_offer_is_allowed(
    guard,
    alice,
    bob,
):
    offer = Offer(

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

    result = guard.check_offer(
        alice,
        offer,
    )

    assert (
        result.action
        == PrivacyAction.ALLOW
    )

    assert result.safe is True


# ============================================================
# OFFER EXCEEDS PRIVATE LIMIT
# ============================================================


def test_offer_above_private_limit_is_blocked(
    guard,
    alice,
    bob,
):
    offer = Offer(

        sender_id=alice.id,
        receiver_id=bob.id,

        offered_resources=[
            Resource(
                resource_type="STORAGE",
                quantity=25,
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

    result = guard.check_offer(
        alice,
        offer,
    )

    assert (
        result.action
        == PrivacyAction.BLOCK
    )

    assert result.safe is False

    assert len(
        result.violations
    ) >= 1


# ============================================================
# BLOCKED PARTNER OFFER
# ============================================================


def test_offer_from_blocked_partner_is_blocked(
    guard,
    alice,
):
    offer = Offer(

        sender_id=alice.id,
        receiver_id="bad-provider-id",

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
                quantity=5,
                unit="gpu-hour",
            )
        ],
    )

    result = guard.check_offer(
        alice,
        offer,
    )

    assert (
        result.action
        == PrivacyAction.BLOCK
    )

    assert result.safe is False


# ============================================================
# REPUTATION CONSTRAINT
# ============================================================


def test_low_reputation_partner_is_blocked(
    guard,
    alice,
    bob,
):
    alice.constraints.minimum_reputation = 0.8

    offer = Offer(

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
                quantity=5,
                unit="gpu-hour",
            )
        ],
    )

    result = guard.check_offer(
        alice,
        offer,
        partner_reputation=0.3,
    )

    assert (
        result.action
        == PrivacyAction.BLOCK
    )

    assert result.safe is False