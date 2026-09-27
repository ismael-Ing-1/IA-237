# app/models/offer.py

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict, model_validator

from app.models.resource import Resource, ResourceRequest


class OfferStatus(str, Enum):
    PENDING = "pending"

    ACCEPTED = "accepted"
    REJECTED = "rejected"

    COUNTERED = "countered"

    EXPIRED = "expired"
    CANCELLED = "cancelled"


class Offer(BaseModel):
    """
    Proposition faite par un agent à un autre agent.

    Exemple :

    Alice donne :
        12 TB de stockage

    Alice demande :
        8 heures de H100

    à Bob.
    """

    model_config = ConfigDict(validate_assignment=True)

    id: str = Field(default_factory=lambda: str(uuid4()))

    # Peut être ajouté après création lorsque
    # l'offre rejoint une négociation.
    negotiation_id: str | None = None

    sender_id: str
    receiver_id: str

    offered_resources: list[Resource] = Field(
        default_factory=list
    )

    requested_resources: list[ResourceRequest] = Field(
        default_factory=list
    )

    status: OfferStatus = OfferStatus.PENDING

    # Si cette offre est une contre-offre,
    # on peut retrouver celle à laquelle elle répond.
    parent_offer_id: str | None = None

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    expires_at: datetime | None = None

    # Message facultatif généré par l'agent.
    message: str | None = None

    @model_validator(mode="after")
    def validate_offer(self) -> "Offer":

        if self.sender_id == self.receiver_id:
            raise ValueError(
                "Un utilisateur ne peut pas créer une offre pour lui-même."
            )

        if (
            len(self.offered_resources) == 0
            and len(self.requested_resources) == 0
        ):
            raise ValueError(
                "Une offre ne peut pas être vide."
            )

        if (
            self.expires_at is not None
            and self.expires_at <= self.created_at
        ):
            raise ValueError(
                "expires_at doit être postérieur à created_at."
            )

        return self

    def is_expired(self) -> bool:
        """
        Vérifie si l'offre est expirée.
        """

        if self.expires_at is None:
            return False

        return datetime.now(timezone.utc) >= self.expires_at

    def mark_accepted(self) -> None:
        self.status = OfferStatus.ACCEPTED

    def mark_rejected(self) -> None:
        self.status = OfferStatus.REJECTED

    def mark_countered(self) -> None:
        self.status = OfferStatus.COUNTERED

    def mark_cancelled(self) -> None:
        self.status = OfferStatus.CANCELLED