from app.models import (
    User,
    Resource,
    ResourceRequest,
    Offer,
    Negotiation,
)

from app.market import (
    MarketRegistry,
    execute_exchange,
)


# --------------------------------------------------
# USERS
# --------------------------------------------------

alice = User(
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


bob = User(
    name="Bob",
    resources=[
        Resource(
            resource_type="H100",
            quantity=20,
            unit="gpu-hour",
        )
    ],
)


# --------------------------------------------------
# REGISTRY
# --------------------------------------------------

registry = MarketRegistry()

registry.register_user(alice)
registry.register_user(bob)


print("\n=== H100 PROVIDERS ===")

providers = registry.find_providers("H100")

for provider in providers:
    print(provider.display_name)


# --------------------------------------------------
# OFFER
# --------------------------------------------------

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
            quantity=8,
            unit="gpu-hour",
        )
    ],
)


# --------------------------------------------------
# NEGOTIATION
# --------------------------------------------------

negotiation = Negotiation(
    participant_ids=[
        alice.id,
        bob.id,
    ]
)

negotiation.add_offer(offer)

negotiation.accept_offer(offer.id)

negotiation.wait_for_human_approval()

negotiation.approve()


# --------------------------------------------------
# BEFORE
# --------------------------------------------------

print("\n=== BEFORE EXCHANGE ===")

print(
    "Alice STORAGE:",
    alice.get_resource_quantity("STORAGE")
)

print(
    "Alice H100:",
    alice.get_resource_quantity("H100")
)

print(
    "Bob STORAGE:",
    bob.get_resource_quantity("STORAGE")
)

print(
    "Bob H100:",
    bob.get_resource_quantity("H100")
)


# --------------------------------------------------
# EXECUTION
# --------------------------------------------------

execute_exchange(
    negotiation=negotiation,
    users=registry.get_all_users(),
)


# --------------------------------------------------
# AFTER
# --------------------------------------------------

print("\n=== AFTER EXCHANGE ===")

print(
    "Alice STORAGE:",
    alice.get_resource_quantity("STORAGE")
)

print(
    "Alice H100:",
    alice.get_resource_quantity("H100")
)

print(
    "Bob STORAGE:",
    bob.get_resource_quantity("STORAGE")
)

print(
    "Bob H100:",
    bob.get_resource_quantity("H100")
)