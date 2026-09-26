# tests/test_reputation.py

import pytest

from app.reputation import (
    ReputationEventType,
    ReputationManager,
)


# ============================================================
# FIXTURE
# ============================================================


@pytest.fixture
def reputation():
    return ReputationManager()


# ============================================================
# REGISTRATION
# ============================================================


def test_register_user(
    reputation,
):
    record = reputation.register_user(
        "alice"
    )

    assert record.user_id == "alice"

    assert (
        record.successful_transactions
        == 0
    )


def test_register_same_user_twice(
    reputation,
):
    first = reputation.register_user(
        "alice"
    )

    second = reputation.register_user(
        "alice"
    )

    assert first is second


# ============================================================
# DEFAULT SCORE
# ============================================================


def test_new_user_has_neutral_score(
    reputation,
):
    score = reputation.get_score(
        "alice"
    )

    assert score == 0.5


# ============================================================
# SUCCESS
# ============================================================


def test_success_increases_reputation(
    reputation,
):
    initial = reputation.get_score(
        "alice"
    )

    reputation.record_success(
        "alice"
    )

    score = reputation.get_score(
        "alice"
    )

    assert score > initial

    assert score == 1.0


def test_success_updates_record(
    reputation,
):
    reputation.record_success(
        "alice"
    )

    record = reputation.get_record(
        "alice"
    )

    assert (
        record.successful_transactions
        == 1
    )

    assert (
        record.delivered_on_time
        == 1
    )


# ============================================================
# FAILURE
# ============================================================


def test_failure_reduces_reputation(
    reputation,
):
    reputation.record_failure(
        "alice"
    )

    score = reputation.get_score(
        "alice"
    )

    assert score < 0.5


def test_failure_updates_record(
    reputation,
):
    reputation.record_failure(
        "alice"
    )

    record = reputation.get_record(
        "alice"
    )

    assert (
        record.failed_transactions
        == 1
    )


# ============================================================
# CANCELLATION
# ============================================================


def test_cancellation_is_less_bad_than_failure(
    reputation,
):
    reputation.record_cancellation(
        "alice"
    )

    reputation.record_failure(
        "bob"
    )

    alice_score = (
        reputation.get_score(
            "alice"
        )
    )

    bob_score = (
        reputation.get_score(
            "bob"
        )
    )

    assert (
        alice_score
        > bob_score
    )


# ============================================================
# LATE DELIVERY
# ============================================================


def test_late_delivery_reduces_score(
    reputation,
):
    reputation.record_success(
        "alice",
        delivered_on_time=True,
    )

    perfect_score = (
        reputation.get_score(
            "alice"
        )
    )

    reputation.record_success(
        "alice",
        delivered_on_time=False,
    )

    new_score = (
        reputation.get_score(
            "alice"
        )
    )

    assert (
        new_score
        < perfect_score
    )


# ============================================================
# MULTIPLE TRANSACTIONS
# ============================================================


def test_mixed_history(
    reputation,
):
    reputation.record_success(
        "alice"
    )

    reputation.record_success(
        "alice"
    )

    reputation.record_failure(
        "alice"
    )

    score = reputation.get_score(
        "alice"
    )

    assert 0 < score < 1


# ============================================================
# SCORE BOUNDS
# ============================================================


def test_score_always_between_zero_and_one(
    reputation,
):
    for _ in range(100):

        reputation.record_failure(
            "alice"
        )

    score = reputation.get_score(
        "alice"
    )

    assert 0 <= score <= 1


# ============================================================
# DIRECT EVENT
# ============================================================


def test_record_event_directly(
    reputation,
):
    reputation.record_event(
        "alice",

        ReputationEventType.TRANSACTION_SUCCESS,
    )

    record = reputation.get_record(
        "alice"
    )

    assert (
        record.successful_transactions
        == 1
    )


# ============================================================
# COMPARISON
# ============================================================


def test_compare_users(
    reputation,
):
    reputation.record_success(
        "alice"
    )

    reputation.record_failure(
        "bob"
    )

    best = reputation.compare_users(
        "alice",
        "bob",
    )

    assert best == "alice"


def test_compare_equal_users(
    reputation,
):
    best = reputation.compare_users(
        "alice",
        "bob",
    )

    assert best is None


# ============================================================
# RANKING
# ============================================================


def test_rank_users(
    reputation,
):
    reputation.record_success(
        "alice"
    )

    reputation.record_success(
        "bob"
    )

    reputation.record_failure(
        "bob"
    )

    reputation.record_failure(
        "charlie"
    )

    ranking = reputation.rank_users(
        [
            "alice",
            "bob",
            "charlie",
        ]
    )

    assert (
        ranking[0][0]
        == "alice"
    )

    assert (
        ranking[-1][0]
        == "charlie"
    )

    assert (
        ranking[0][1]
        >= ranking[1][1]
        >= ranking[2][1]
    )