# app/market/exchange.py

from __future__ import annotations

from app.models import (
    User,
    Resource,
    ResourceRequest,
    Offer,
    Negotiation,
    NegotiationStatus,
)


class ExchangeError(Exception):
    """
    Exception spécifique aux erreurs d'exécution d'un échange.
    """


def _available_quantity(
    user: User,
    resource_type: str,
    unit: str
) -> float:
    """
    Retourne la quantité réellement disponible d'une ressource
    pour un utilisateur.

    Le type ET l'unité doivent correspondre.
    """

    return sum(
        resource.quantity
        for resource in user.resources
        if (
            resource.resource_type.lower()
            == resource_type.lower()
            and resource.unit.lower()
            == unit.lower()
        )
    )


def _has_resource(
    user: User,
    resource_type: str,
    quantity: float,
    unit: str
) -> bool:
    """
    Vérifie qu'un utilisateur possède suffisamment
    d'une ressource donnée.
    """

    return (
        _available_quantity(
            user=user,
            resource_type=resource_type,
            unit=unit,
        )
        >= quantity
    )


def _remove_resource_quantity(
    user: User,
    resource_type: str,
    quantity: float,
    unit: str
) -> None:
    """
    Retire une quantité de ressource de l'inventaire d'un utilisateur.

    La ressource peut être répartie sur plusieurs entrées.

    Exemple :

        Alice possède :
            H100 : 3
            H100 : 5

        retirer 6

        résultat :
            premier lot supprimé
            second lot = 2
    """

    if not _has_resource(
        user=user,
        resource_type=resource_type,
        quantity=quantity,
        unit=unit,
    ):
        raise ExchangeError(
            f"{user.name} ne possède pas suffisamment "
            f"de {resource_type}."
        )

    remaining_to_remove = quantity

    for resource in list(user.resources):

        if remaining_to_remove <= 0:
            break

        if (
            resource.resource_type.lower()
            != resource_type.lower()
        ):
            continue

        if resource.unit.lower() != unit.lower():
            continue

        amount_taken = min(
            resource.quantity,
            remaining_to_remove
        )

        resource.quantity -= amount_taken
        remaining_to_remove -= amount_taken

        # Si le lot est vide, on le supprime.
        if resource.quantity <= 0:
            user.resources.remove(resource)


def _add_resource_quantity(
    user: User,
    resource_type: str,
    quantity: float,
    unit: str
) -> None:
    """
    Ajoute une ressource à l'inventaire d'un utilisateur.

    Si une ressource compatible existe déjà,
    sa quantité est augmentée.

    Sinon, une nouvelle ressource est créée.
    """

    for resource in user.resources:

        if (
            resource.resource_type.lower()
            == resource_type.lower()
            and resource.unit.lower()
            == unit.lower()
        ):
            resource.quantity += quantity
            return

    user.resources.append(
        Resource(
            resource_type=resource_type,
            quantity=quantity,
            unit=unit,
        )
    )


def _validate_offer_resources(
    offer: Offer,
    sender: User,
    receiver: User
) -> None:
    """
    Vérifie que les deux utilisateurs possèdent encore
    les ressources qu'ils se sont engagés à échanger.

    Alice offre :
        STORAGE

    Alice demande :
        H100

    Donc :

        Alice doit posséder STORAGE.
        Bob doit posséder H100.
    """

    # Ressources promises par le sender.
    for resource in offer.offered_resources:

        if not _has_resource(
            user=sender,
            resource_type=resource.resource_type,
            quantity=resource.quantity,
            unit=resource.unit,
        ):
            raise ExchangeError(
                f"{sender.name} ne possède plus suffisamment "
                f"de {resource.resource_type}."
            )

    # Ressources demandées au receiver.
    for request in offer.requested_resources:

        if not _has_resource(
            user=receiver,
            resource_type=request.resource_type,
            quantity=request.quantity,
            unit=request.unit,
        ):
            raise ExchangeError(
                f"{receiver.name} ne possède pas suffisamment "
                f"de {request.resource_type}."
            )


def _execute_offer_transfer(
    offer: Offer,
    sender: User,
    receiver: User
) -> None:
    """
    Exécute les transferts définis par une offre.

    sender
        donne offered_resources
        reçoit requested_resources

    receiver
        reçoit offered_resources
        donne requested_resources
    """

    # --------------------------------------------------------------
    # Sender -> Receiver
    # --------------------------------------------------------------

    for resource in offer.offered_resources:

        _remove_resource_quantity(
            user=sender,
            resource_type=resource.resource_type,
            quantity=resource.quantity,
            unit=resource.unit,
        )

        _add_resource_quantity(
            user=receiver,
            resource_type=resource.resource_type,
            quantity=resource.quantity,
            unit=resource.unit,
        )

    # --------------------------------------------------------------
    # Receiver -> Sender
    # --------------------------------------------------------------

    for request in offer.requested_resources:

        _remove_resource_quantity(
            user=receiver,
            resource_type=request.resource_type,
            quantity=request.quantity,
            unit=request.unit,
        )

        _add_resource_quantity(
            user=sender,
            resource_type=request.resource_type,
            quantity=request.quantity,
            unit=request.unit,
        )


def execute_exchange(
    negotiation: Negotiation,
    users: dict[str, User]
) -> bool:
    """
    Exécute l'échange final d'une négociation.

    Preconditions :

        negotiation.status == APPROVED

        negotiation.accepted_offer_id existe

        sender et receiver existent

        chacun possède toujours les ressources promises

    Retourne :

        True si l'échange a été exécuté.

    Lève ExchangeError sinon.
    """

    # --------------------------------------------------------------
    # 1. Vérifier la validation humaine
    # --------------------------------------------------------------

    if negotiation.status != NegotiationStatus.APPROVED:
        raise ExchangeError(
            "La négociation doit être approuvée "
            "avant d'exécuter l'échange."
        )

    # --------------------------------------------------------------
    # 2. Vérifier qu'une offre a été acceptée
    # --------------------------------------------------------------

    if negotiation.accepted_offer_id is None:
        raise ExchangeError(
            "Aucune offre n'a été acceptée."
        )

    offer = negotiation.get_offer(
        negotiation.accepted_offer_id
    )

    if offer is None:
        raise ExchangeError(
            "L'offre acceptée est introuvable."
        )

    # --------------------------------------------------------------
    # 3. Récupérer les participants
    # --------------------------------------------------------------

    sender = users.get(offer.sender_id)
    receiver = users.get(offer.receiver_id)

    if sender is None:
        raise ExchangeError(
            f"Sender {offer.sender_id} introuvable."
        )

    if receiver is None:
        raise ExchangeError(
            f"Receiver {offer.receiver_id} introuvable."
        )

    # --------------------------------------------------------------
    # 4. Vérifier toutes les ressources AVANT toute modification
    # --------------------------------------------------------------

    _validate_offer_resources(
        offer=offer,
        sender=sender,
        receiver=receiver,
    )

    # --------------------------------------------------------------
    # 5. Exécuter le transfert
    # --------------------------------------------------------------

    _execute_offer_transfer(
        offer=offer,
        sender=sender,
        receiver=receiver,
    )

    return True