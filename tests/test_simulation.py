# tests/test_simulation.py

from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    User,
    Resource,
    ResourceRequest,
)

from app.models.negotiation import (
    NegotiationStatus,
)

from app.simulation import (
    SimulationWorld,
    MarketEvent,
    EventType,
)

from app.tools.negotiation_tools import (
    create_negotiation,
    send_offer,
    accept_offer,
    request_human_approval,
    approve_negotiation,
)


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def start_time():
    return datetime(
        2026,
        9,
        26,
        9,
        0,
        tzinfo=timezone.utc,
    )


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
                resource_type="A100",
                quantity=5,
                unit="gpu-hour",
            )
        ],
    )


@pytest.fixture
def world(start_time, alice, bob):
    world = SimulationWorld(
        start_time=start_time
    )

    world.add_user(alice)
    world.add_user(bob)

    return world


# ============================================================
# EVENT VALIDATION
# ============================================================


def test_resource_added_event_requires_resource(
    start_time,
    alice,
):
    with pytest.raises(ValueError):

        MarketEvent(
            event_type=EventType.RESOURCE_ADDED,
            user_id=alice.id,
            scheduled_at=start_time,
        )


def test_resource_removed_requires_resource_id(
    start_time,
    alice,
):
    with pytest.raises(ValueError):

        MarketEvent(
            event_type=EventType.RESOURCE_REMOVED,
            user_id=alice.id,
            scheduled_at=start_time,
        )


def test_need_added_requires_need(
    start_time,
    alice,
):
    with pytest.raises(ValueError):

        MarketEvent(
            event_type=EventType.NEED_ADDED,
            user_id=alice.id,
            scheduled_at=start_time,
        )


def test_need_removed_requires_need_id(
    start_time,
    alice,
):
    with pytest.raises(ValueError):

        MarketEvent(
            event_type=EventType.NEED_REMOVED,
            user_id=alice.id,
            scheduled_at=start_time,
        )


def test_event_requires_timezone(
    alice,
):
    naive_date = datetime(
        2026,
        9,
        26,
        10,
        0,
    )

    with pytest.raises(ValueError):

        MarketEvent(
            event_type=EventType.USER_OFFLINE,
            user_id=alice.id,
            scheduled_at=naive_date,
        )


# ============================================================
# WORLD INITIALIZATION
# ============================================================


def test_world_initial_time(
    world,
    start_time,
):
    assert world.current_time == start_time


def test_world_contains_users(
    world,
    alice,
    bob,
):
    assert world.get_user(
        alice.id
    ) is alice

    assert world.get_user(
        bob.id
    ) is bob

    assert len(
        world.get_users()
    ) == 2


def test_duplicate_user_is_rejected(
    world,
    alice,
):
    with pytest.raises(ValueError):

        world.add_user(
            alice
        )


# ============================================================
# VIRTUAL TIME
# ============================================================


def test_advance_time(
    world,
    start_time,
):
    world.advance_time(
        minutes=30
    )

    assert world.current_time == (
        start_time
        + timedelta(minutes=30)
    )


def test_time_cannot_go_backward(
    world,
):
    with pytest.raises(ValueError):

        world.advance_time(
            minutes=-1
        )


def test_run_until_cannot_go_backward(
    world,
    start_time,
):
    past = (
        start_time
        - timedelta(minutes=1)
    )

    with pytest.raises(ValueError):

        world.run_until(
            past
        )


# ============================================================
# EVENT SCHEDULING
# ============================================================


def test_schedule_future_event(
    world,
    bob,
):
    event = MarketEvent(
        event_type=EventType.USER_OFFLINE,
        user_id=bob.id,

        scheduled_at=(
            world.current_time
            + timedelta(minutes=10)
        ),
    )

    world.schedule_event(
        event
    )

    events = (
        world.get_scheduled_events()
    )

    assert len(events) == 1
    assert events[0].id == event.id


def test_cannot_schedule_event_in_past(
    world,
    bob,
):
    event = MarketEvent(
        event_type=EventType.USER_OFFLINE,
        user_id=bob.id,

        scheduled_at=(
            world.current_time
            - timedelta(minutes=1)
        ),
    )

    with pytest.raises(ValueError):

        world.schedule_event(
            event
        )


def test_schedule_event_in_helper(
    world,
    bob,
):
    event = world.schedule_event_in(
        delay=timedelta(
            minutes=15
        ),

        event_type=EventType.USER_OFFLINE,

        user_id=bob.id,
    )

    assert event.scheduled_at == (
        world.current_time
        + timedelta(minutes=15)
    )


# ============================================================
# ONLINE / OFFLINE
# ============================================================


def test_user_goes_offline(
    world,
    bob,
):
    world.schedule_event_in(
        delay=timedelta(
            minutes=5
        ),

        event_type=EventType.USER_OFFLINE,

        user_id=bob.id,
    )

    assert bob.online is True

    world.advance_time(
        minutes=5
    )

    assert bob.online is False


def test_user_goes_online_again(
    world,
    bob,
):
    bob.online = False

    world.schedule_event_in(
        delay=timedelta(
            minutes=5
        ),

        event_type=EventType.USER_ONLINE,

        user_id=bob.id,
    )

    world.advance_time(
        minutes=5
    )

    assert bob.online is True


# ============================================================
# RESOURCE ADDED
# ============================================================


def test_resource_added_event(
    world,
    bob,
):
    assert (
        bob.get_resource_quantity(
            "H100"
        )
        == 20
    )

    world.schedule_event_in(
        delay=timedelta(
            minutes=10
        ),

        event_type=EventType.RESOURCE_ADDED,

        user_id=bob.id,

        resource=Resource(
            resource_type="H100",
            quantity=10,
            unit="gpu-hour",
        ),
    )

    world.advance_time(
        minutes=10
    )

    assert (
        bob.get_resource_quantity(
            "H100"
        )
        == 30
    )


# ============================================================
# RESOURCE REMOVAL
# ============================================================


def test_partial_resource_removal(
    world,
    bob,
):
    resource = bob.resources[0]

    world.schedule_event_in(
        delay=timedelta(
            minutes=5
        ),

        event_type=EventType.RESOURCE_REMOVED,

        user_id=bob.id,

        resource_id=resource.id,

        quantity=5,
    )

    world.advance_time(
        minutes=5
    )

    assert (
        bob.get_resource_quantity(
            "H100"
        )
        == 15
    )


def test_complete_resource_removal(
    world,
    bob,
):
    resource = bob.resources[0]

    world.schedule_event_in(
        delay=timedelta(
            minutes=5
        ),

        event_type=EventType.RESOURCE_REMOVED,

        user_id=bob.id,

        resource_id=resource.id,
    )

    world.advance_time(
        minutes=5
    )

    assert (
        bob.get_resource_quantity(
            "H100"
        )
        == 0
    )


def test_remove_too_much_resource_fails(
    world,
    bob,
):
    resource = bob.resources[0]

    world.schedule_event_in(
        delay=timedelta(
            minutes=5
        ),

        event_type=EventType.RESOURCE_REMOVED,

        user_id=bob.id,

        resource_id=resource.id,

        quantity=100,
    )

    executions = (
        world.advance_time(
            minutes=5
        )
    )

    assert len(executions) == 1

    assert (
        executions[0].success
        is False
    )

    assert (
        bob.get_resource_quantity(
            "H100"
        )
        == 20
    )


# ============================================================
# RESOURCE EXPIRATION
# ============================================================


def test_resource_expiration(
    world,
    bob,
):
    resource = bob.resources[0]

    world.schedule_event_in(
        delay=timedelta(
            minutes=30
        ),

        event_type=EventType.RESOURCE_EXPIRED,

        user_id=bob.id,

        resource_id=resource.id,
    )

    world.advance_time(
        minutes=30
    )

    assert (
        bob.get_resource_quantity(
            "H100"
        )
        == 0
    )


# ============================================================
# NEED EVENTS
# ============================================================


def test_need_added(
    world,
    bob,
):
    initial_count = len(
        bob.needs
    )

    new_need = ResourceRequest(
        resource_type="STORAGE",
        quantity=10,
        unit="TB-day",
    )

    world.schedule_event_in(
        delay=timedelta(
            minutes=5
        ),

        event_type=EventType.NEED_ADDED,

        user_id=bob.id,

        need=new_need,
    )

    world.advance_time(
        minutes=5
    )

    assert len(
        bob.needs
    ) == initial_count + 1

    assert any(
        need.id == new_need.id
        for need in bob.needs
    )


def test_need_removed(
    world,
    bob,
):
    need = bob.needs[0]

    world.schedule_event_in(
        delay=timedelta(
            minutes=5
        ),

        event_type=EventType.NEED_REMOVED,

        user_id=bob.id,

        need_id=need.id,
    )

    world.advance_time(
        minutes=5
    )

    assert all(
        existing_need.id
        != need.id

        for existing_need
        in bob.needs
    )


# ============================================================
# MULTIPLE EVENTS / ORDER
# ============================================================


def test_events_execute_in_chronological_order(
    world,
    bob,
):
    world.schedule_event_in(
        delay=timedelta(
            minutes=30
        ),

        event_type=EventType.USER_ONLINE,

        user_id=bob.id,
    )

    world.schedule_event_in(
        delay=timedelta(
            minutes=10
        ),

        event_type=EventType.USER_OFFLINE,

        user_id=bob.id,
    )

    executions = (
        world.advance_time(
            minutes=40
        )
    )

    assert len(
        executions
    ) == 2

    assert (
        executions[0].event_type
        == EventType.USER_OFFLINE
    )

    assert (
        executions[1].event_type
        == EventType.USER_ONLINE
    )

    assert bob.online is True


def test_same_time_events_are_all_executed(
    world,
    bob,
):
    execution_time = (
        world.current_time
        + timedelta(minutes=10)
    )

    event1 = MarketEvent(
        event_type=EventType.USER_OFFLINE,
        user_id=bob.id,
        scheduled_at=execution_time,
    )

    event2 = MarketEvent(
        event_type=EventType.USER_ONLINE,
        user_id=bob.id,
        scheduled_at=execution_time,
    )

    world.schedule_event(
        event1
    )

    world.schedule_event(
        event2
    )

    executions = (
        world.advance_time(
            minutes=10
        )
    )

    assert len(
        executions
    ) == 2


# ============================================================
# EVENTS ONLY FIRE WHEN TIME REACHES THEM
# ============================================================


def test_event_not_executed_too_early(
    world,
    bob,
):
    world.schedule_event_in(
        delay=timedelta(
            minutes=30
        ),

        event_type=EventType.USER_OFFLINE,

        user_id=bob.id,
    )

    world.advance_time(
        minutes=29
    )

    assert bob.online is True

    world.advance_time(
        minutes=1
    )

    assert bob.online is False


# ============================================================
# EVENT HISTORY
# ============================================================


def test_event_history(
    world,
    bob,
):
    world.schedule_event_in(
        delay=timedelta(
            minutes=5
        ),

        event_type=EventType.USER_OFFLINE,

        user_id=bob.id,
    )

    world.advance_time(
        minutes=5
    )

    assert len(
        world.event_history
    ) == 1

    execution = (
        world.event_history[0]
    )

    assert execution.success is True

    assert (
        execution.event_type
        == EventType.USER_OFFLINE
    )


# ============================================================
# UNKNOWN USER
# ============================================================


def test_event_for_unknown_user_fails(
    world,
):
    world.schedule_event_in(
        delay=timedelta(
            minutes=5
        ),

        event_type=EventType.USER_OFFLINE,

        user_id="unknown-user",
    )

    executions = (
        world.advance_time(
            minutes=5
        )
    )

    assert len(
        executions
    ) == 1

    assert (
        executions[0].success
        is False
    )


# ============================================================
# RUN UNTIL
# ============================================================


def test_run_until_executes_events(
    world,
    bob,
):
    event_time = (
        world.current_time
        + timedelta(minutes=20)
    )

    world.schedule_event(
        MarketEvent(
            event_type=EventType.USER_OFFLINE,
            user_id=bob.id,
            scheduled_at=event_time,
        )
    )

    target = (
        world.current_time
        + timedelta(hours=1)
    )

    executions = (
        world.run_until(
            target
        )
    )

    assert len(
        executions
    ) == 1

    assert bob.online is False

    assert (
        world.current_time
        == target
    )


# ============================================================
# NEGOTIATION STORAGE
# ============================================================


def test_add_and_get_negotiation(
    world,
    alice,
    bob,
):
    negotiation = (
        create_negotiation(
            [
                alice.id,
                bob.id,
            ]
        )
    )

    world.add_negotiation(
        negotiation
    )

    recovered = (
        world.get_negotiation(
            negotiation.id
        )
    )

    assert recovered is negotiation

    assert len(
        world.get_active_negotiations()
    ) == 1


def test_duplicate_negotiation_rejected(
    world,
    alice,
    bob,
):
    negotiation = (
        create_negotiation(
            [
                alice.id,
                bob.id,
            ]
        )
    )

    world.add_negotiation(
        negotiation
    )

    with pytest.raises(ValueError):

        world.add_negotiation(
            negotiation
        )


# ============================================================
# APPROVED NEGOTIATION
# ============================================================


def test_world_requires_approved_negotiation_before_execution(
    world,
    alice,
    bob,
):
    negotiation = (
        create_negotiation(
            [
                alice.id,
                bob.id,
            ]
        )
    )

    world.add_negotiation(
        negotiation
    )

    assert (
        negotiation.status
        == NegotiationStatus.OPEN
    )

    with pytest.raises(ValueError):

        world.execute_negotiation(
            negotiation.id
        )


# ============================================================
# FULL NEGOTIATION + EXCHANGE
# ============================================================


def test_full_exchange_through_world(
    world,
    alice,
    bob,
):
    """
    Vérifie :

    simulation
        +
    negotiation
        +
    approval
        +
    exchange
    """

    negotiation = (
        create_negotiation(
            [
                alice.id,
                bob.id,
            ]
        )
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

    assert (
        negotiation.status
        == NegotiationStatus.APPROVED
    )

    alice_storage_before = (
        alice.get_resource_quantity(
            "STORAGE"
        )
    )

    bob_h100_before = (
        bob.get_resource_quantity(
            "H100"
        )
    )

    success = (
        world.execute_negotiation(
            negotiation.id
        )
    )

    assert success is True

    assert (
        alice.get_resource_quantity(
            "STORAGE"
        )
        == alice_storage_before - 10
    )

    assert (
        alice.get_resource_quantity(
            "H100"
        )
        == 8
    )

    assert (
        bob.get_resource_quantity(
            "H100"
        )
        == bob_h100_before - 8
    )

    assert (
        bob.get_resource_quantity(
            "STORAGE"
        )
        == 10
    )

    # La négociation n'est plus active.

    assert (
        negotiation.id
        not in world.active_negotiations
    )

    # Elle est désormais archivée.

    assert (
        negotiation.id
        in world.completed_negotiations
    )