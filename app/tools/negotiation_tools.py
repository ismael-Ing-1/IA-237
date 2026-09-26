# app/tools/negotiation_tools.py

from __future__ import annotations

from datetime import datetime

from app.models.resource import Resource, ResourceRequest
from app.models.offer import Offer, OfferStatus
from app.models.negotiation import (
    Negotiation,
    NegotiationStatus,
)


def create_negotiation(
    participant_ids: list[str],
    max_rounds: int = 10
) -> Negotiation:
    """
    Crée une nouvelle négociation.

    Exemple :

        negotiation = create_negotiation(
            [alice.id, bob.id]
        )
    """

    return Negotiation(
        participant_ids=participant_ids,
        max_rounds=max_rounds
    )


def send_offer(
    negotiation: Negotiation,
    sender_id: str,
    receiver_id: str,
    offered_resources: list[Resource],
    requested_resources: list[ResourceRequest],
    message: str | None = None,
    expires_at: datetime | None = None,
) -> Offer:
    """
    Crée et envoie une nouvelle offre dans une négociation.

    Retourne l'objet Offer créé.
    """

    offer = Offer(
        negotiation_id=negotiation.id,

        sender_id=sender_id,
        receiver_id=receiver_id,

        offered_resources=offered_resources,
        requested_resources=requested_resources,

        message=message,
        expires_at=expires_at
    )

    negotiation.add_offer(offer)

    return offer


def counter_offer(
    negotiation: Negotiation,
    previous_offer_id: str,
    sender_id: str,
    receiver_id: str,
    offered_resources: list[Resource],
    requested_resources: list[ResourceRequest],
    message: str | None = None,
    expires_at: datetime | None = None,
) -> Offer:
    """
    Répond à une offre existante par une contre-offre.

    Exemple :

        Alice : 10 TB
        Bob   : 15 TB
        Alice : 12 TB
    """

    previous_offer = negotiation.get_offer(
        previous_offer_id
    )

    if previous_offer is None:
        raise ValueError(
            f"Offre {previous_offer_id} introuvable."
        )

    if previous_offer.is_expired():
        previous_offer.status = OfferStatus.EXPIRED

        raise ValueError(
            "Impossible de répondre à une offre expirée."
        )

    if previous_offer.status not in {
        OfferStatus.PENDING,
        OfferStatus.COUNTERED,
    }:
        raise ValueError(
            "Cette offre ne peut plus recevoir de contre-offre."
        )

    previous_offer.mark_countered()

    new_offer = Offer(
        negotiation_id=negotiation.id,

        sender_id=sender_id,
        receiver_id=receiver_id,

        offered_resources=offered_resources,
        requested_resources=requested_resources,

        parent_offer_id=previous_offer.id,

        message=message,
        expires_at=expires_at
    )

    negotiation.add_offer(new_offer)

    return new_offer


def accept_offer(
    negotiation: Negotiation,
    offer_id: str
) -> Offer:
    """
    Accepte une offre du point de vue des agents.

    Cela signifie :

        AGREEMENT_FOUND

    et PAS encore :

        transaction exécutée.

    Une validation humaine peut encore être nécessaire.
    """

    offer = negotiation.get_offer(offer_id)

    if offer is None:
        raise ValueError(
            f"Offre {offer_id} introuvable."
        )

    if offer.is_expired():
        offer.status = OfferStatus.EXPIRED

        raise ValueError(
            "Impossible d'accepter une offre expirée."
        )

    return negotiation.accept_offer(offer_id)


def reject_offer(
    negotiation: Negotiation,
    offer_id: str,
    close_negotiation: bool = False
) -> Offer:
    """
    Refuse une offre.

    Par défaut, la négociation reste ouverte :
    l'agent pourra essayer une autre offre.

    Si close_negotiation=True, toute la négociation
    est marquée comme REJECTED.
    """

    offer = negotiation.get_offer(offer_id)

    if offer is None:
        raise ValueError(
            f"Offre {offer_id} introuvable."
        )

    offer.mark_rejected()

    if close_negotiation:
        negotiation.reject()

    elif negotiation.status not in {
        NegotiationStatus.CANCELLED,
        NegotiationStatus.FAILED,
    }:
        negotiation.status = NegotiationStatus.NEGOTIATING

    return offer


def request_human_approval(
    negotiation: Negotiation
) -> None:
    """
    Passe la négociation dans :

        WAITING_HUMAN

    Un accord entre agents doit déjà avoir été trouvé.
    """

    negotiation.wait_for_human_approval()


def approve_negotiation(
    negotiation: Negotiation
) -> None:
    """
    L'utilisateur humain approuve l'accord.
    """

    negotiation.approve()


def reject_negotiation(
    negotiation: Negotiation
) -> None:
    """
    L'utilisateur refuse l'accord.
    """

    negotiation.reject()


def cancel_negotiation(
    negotiation: Negotiation
) -> None:
    """
    Annule complètement la négociation.
    """

    negotiation.cancel()


def get_negotiation_history(
    negotiation: Negotiation
) -> list[Offer]:
    """
    Retourne les offres dans leur ordre chronologique.
    """

    return list(negotiation.offers)


def get_last_offer(
    negotiation: Negotiation
) -> Offer | None:
    """
    Retourne la dernière offre de la négociation.
    """

    return negotiation.get_last_offer()