# app/models/negotiation.py

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict, model_validator

from app.models.offer import Offer, OfferStatus


class NegotiationStatus(str, Enum):
    OPEN = "open"

    NEGOTIATING = "negotiating"

    AGREEMENT_FOUND = "agreement_found"

    WAITING_HUMAN = "waiting_human"

    APPROVED = "approved"

    REJECTED = "rejected"

    CANCELLED = "cancelled"

    FAILED = "failed"


class Negotiation(BaseModel):
    """
    Contient l'ensemble des échanges entre plusieurs agents.

    Pour l'instant, une négociation peut avoir 2 participants ou plus,
    ce qui permettra plus tard les coalitions.
    """

    model_config = ConfigDict(validate_assignment=True)

    id: str = Field(default_factory=lambda: str(uuid4()))

    participant_ids: list[str] = Field(
        ...,
        min_length=2
    )

    offers: list[Offer] = Field(
        default_factory=list
    )

    status: NegotiationStatus = NegotiationStatus.OPEN

    current_round: int = Field(
        default=0,
        ge=0
    )

    max_rounds: int = Field(
        default=10,
        ge=1
    )

    accepted_offer_id: str | None = None

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @model_validator(mode="after")
    def validate_participants(self) -> "Negotiation":

        if len(set(self.participant_ids)) < 2:
            raise ValueError(
                "Une négociation doit avoir au moins deux participants distincts."
            )

        return self

    def add_offer(self, offer: Offer) -> None:
        """
        Ajoute une nouvelle offre à la négociation.
        """

        if self.status in {
            NegotiationStatus.APPROVED,
            NegotiationStatus.CANCELLED,
            NegotiationStatus.FAILED,
            NegotiationStatus.REJECTED,
        }:
            raise ValueError(
                f"Impossible d'ajouter une offre à une négociation "
                f"dans l'état {self.status}."
            )

        if offer.sender_id not in self.participant_ids:
            raise ValueError(
                "Le sender de l'offre ne participe pas à cette négociation."
            )

        if offer.receiver_id not in self.participant_ids:
            raise ValueError(
                "Le receiver de l'offre ne participe pas à cette négociation."
            )

        if self.current_round >= self.max_rounds:
            self.status = NegotiationStatus.FAILED
            raise ValueError(
                "Nombre maximal de tours de négociation atteint."
            )

        offer.negotiation_id = self.id

        self.offers.append(offer)

        self.current_round += 1

        self.status = NegotiationStatus.NEGOTIATING

        self.updated_at = datetime.now(timezone.utc)

    def get_last_offer(self) -> Offer | None:
        """
        Retourne la dernière offre envoyée.
        """

        if not self.offers:
            return None

        return self.offers[-1]

    def get_offer(
        self,
        offer_id: str
    ) -> Offer | None:
        """
        Recherche une offre à partir de son ID.
        """

        for offer in self.offers:
            if offer.id == offer_id:
                return offer

        return None

    def accept_offer(
        self,
        offer_id: str
    ) -> Offer:
        """
        L'agent considère qu'un accord a été trouvé.

        Attention :
        cela ne signifie PAS encore que l'utilisateur humain
        a validé l'échange.
        """

        offer = self.get_offer(offer_id)

        if offer is None:
            raise ValueError(
                f"Offre {offer_id} introuvable."
            )

        offer.status = OfferStatus.ACCEPTED

        self.accepted_offer_id = offer.id

        self.status = NegotiationStatus.AGREEMENT_FOUND

        self.updated_at = datetime.now(timezone.utc)

        return offer

    def wait_for_human_approval(self) -> None:
        """
        Passe à l'étape human-in-the-loop.
        """

        if self.accepted_offer_id is None:
            raise ValueError(
                "Impossible de demander une validation humaine "
                "sans accord préalable."
            )

        self.status = NegotiationStatus.WAITING_HUMAN
        self.updated_at = datetime.now(timezone.utc)

    def approve(self) -> None:
        """
        Validation finale par l'utilisateur.
        """

        if self.status != NegotiationStatus.WAITING_HUMAN:
            raise ValueError(
                "La négociation n'attend pas de validation humaine."
            )

        self.status = NegotiationStatus.APPROVED
        self.updated_at = datetime.now(timezone.utc)

    def reject(self) -> None:
        self.status = NegotiationStatus.REJECTED
        self.updated_at = datetime.now(timezone.utc)

    def cancel(self) -> None:
        self.status = NegotiationStatus.CANCELLED
        self.updated_at = datetime.now(timezone.utc)

    def fail(self) -> None:
        self.status = NegotiationStatus.FAILED
        self.updated_at = datetime.now(timezone.utc)