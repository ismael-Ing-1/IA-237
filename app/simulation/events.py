# app/simulation/events.py

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.models.resource import (
    Resource,
    ResourceRequest,
)


class EventType(str, Enum):
    """
    Types d'événements pouvant arriver dans le marché.
    """

    RESOURCE_ADDED = "resource_added"
    RESOURCE_REMOVED = "resource_removed"
    RESOURCE_EXPIRED = "resource_expired"

    NEED_ADDED = "need_added"
    NEED_REMOVED = "need_removed"

    USER_ONLINE = "user_online"
    USER_OFFLINE = "user_offline"


class MarketEvent(BaseModel):
    """
    Représente un événement programmé dans le temps virtuel.

    Exemples :

    - Bob ajoute 10 H100 dans 20 minutes.
    - Charlie devient offline dans 5 minutes.
    - Une ressource expire dans 1 heure.
    """

    model_config = ConfigDict(validate_assignment=True)

    id: str = Field(
        default_factory=lambda: str(uuid4())
    )

    event_type: EventType

    user_id: str

    # Instant VIRTUEL auquel l'événement doit se produire.
    scheduled_at: datetime

    # RESOURCE_ADDED
    resource: Resource | None = None

    # RESOURCE_REMOVED / RESOURCE_EXPIRED
    resource_id: str | None = None

    # Si renseigné, permet de retirer seulement une partie
    # de la quantité disponible.
    quantity: float | None = Field(
        default=None,
        gt=0,
    )

    # NEED_ADDED
    need: ResourceRequest | None = None

    # NEED_REMOVED
    need_id: str | None = None

    reason: str | None = None

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_event(self) -> "MarketEvent":

        if (
            self.scheduled_at.tzinfo is None
            or self.scheduled_at.utcoffset() is None
        ):
            raise ValueError(
                "scheduled_at doit contenir un timezone."
            )

        if (
            self.event_type
            == EventType.RESOURCE_ADDED
            and self.resource is None
        ):
            raise ValueError(
                "RESOURCE_ADDED nécessite resource."
            )

        if self.event_type in {
            EventType.RESOURCE_REMOVED,
            EventType.RESOURCE_EXPIRED,
        }:
            if self.resource_id is None:
                raise ValueError(
                    f"{self.event_type} nécessite resource_id."
                )

        if (
            self.event_type
            == EventType.NEED_ADDED
            and self.need is None
        ):
            raise ValueError(
                "NEED_ADDED nécessite need."
            )

        if (
            self.event_type
            == EventType.NEED_REMOVED
            and self.need_id is None
        ):
            raise ValueError(
                "NEED_REMOVED nécessite need_id."
            )

        return self


class EventExecution(BaseModel):
    """
    Résultat de l'exécution d'un événement.
    """

    event_id: str

    event_type: EventType

    user_id: str

    executed_at: datetime = Field(
        default_factory=lambda: datetime.now(
            timezone.utc
        )
    )

    success: bool

    message: str