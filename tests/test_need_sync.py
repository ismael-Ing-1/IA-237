from app.models.resource import ResourceRequest
from app.models.user import User
from app.tools.need_tools import sync_user_need, satisfy_user_need


def test_editing_existing_need_updates_quantity_without_duplicate():
    user = User(
        id="alice",
        name="Alice",
        needs=[
            ResourceRequest(
                id="alice-h100",
                resource_type="H100",
                quantity=8,
                unit="gpu-hour",
            )
        ],
    )

    updated = sync_user_need(
        user,
        ResourceRequest(
            id="alice-h100",
            resource_type="H100",
            quantity=5,
            unit="gpu-hour",
        ),
    )

    assert updated.quantity == 5
    assert len(user.needs) == 1
    assert user.needs[0].quantity == 5


def test_partial_settlement_reduces_remaining_need():
    user = User(
        id="alice",
        name="Alice",
        needs=[
            ResourceRequest(
                resource_type="H100",
                quantity=8,
                unit="gpu-hour",
            )
        ],
    )

    satisfy_user_need(
        user,
        resource_type="H100",
        unit="gpu-hour",
        quantity=3,
    )

    assert len(user.needs) == 1
    assert user.needs[0].quantity == 5


def test_full_settlement_removes_active_need():
    user = User(
        id="alice",
        name="Alice",
        needs=[
            ResourceRequest(
                resource_type="H100",
                quantity=8,
                unit="gpu-hour",
            )
        ],
    )

    satisfy_user_need(
        user,
        resource_type="H100",
        unit="gpu-hour",
        quantity=8,
    )

    assert user.needs == []
