# app/tools/privacy_tools.py

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.models.user import User
from app.models.offer import Offer


class MarginLevel(str, Enum):
    """
    Niveau approximatif de marge restant à l'utilisateur.

    Le but est de donner une information utile à l'agent
    sans exposer la limite privée exacte.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class PrivacyDecision(BaseModel):
    """
    Résultat d'une vérification de contraintes privées.

    Les raisons sont volontairement génériques pour ne pas
    révéler les seuils exacts.
    """

    allowed: bool

    reasons: list[str] = Field(
        default_factory=list
    )


def can_user_give(
    user: User,
    resource_type: str,
    quantity: float
) -> bool:
    """
    Vérifie si un utilisateur peut céder une certaine quantité
    d'une ressource.

    Vérifie à la fois :

    1. son inventaire réel ;
    2. sa limite privée max_quantity_to_give.
    """

    if quantity <= 0:
        return False

    available_quantity = user.get_resource_quantity(
        resource_type
    )

    if available_quantity < quantity:
        return False

    private_limit = (
        user.constraints
        .max_quantity_to_give
        .get(resource_type)
    )

    if (
        private_limit is not None
        and quantity > private_limit
    ):
        return False

    return True


def is_partner_allowed(
    user: User,
    partner_id: str,
    partner_reputation: float | None = None
) -> bool:
    """
    Vérifie si l'utilisateur accepte de négocier avec ce partenaire.

    Le partenaire peut être refusé si :

    - il est explicitement bloqué ;
    - sa réputation est inférieure au minimum accepté.
    """

    if partner_id in user.blocked_partners:
        return False

    if (
        partner_reputation is not None
        and partner_reputation
        < user.constraints.minimum_reputation
    ):
        return False

    return True


def is_partner_preferred(
    user: User,
    partner_a_id: str,
    partner_b_id: str
) -> bool:
    """
    Compare deux partenaires sans révéler toute la liste
    privée des préférences.

    Retourne True si A est préféré à B.
    """

    return user.prefers(
        partner_a_id,
        partner_b_id
    )


def _get_resources_given_by_user(
    user: User,
    offer: Offer
) -> list[tuple[str, float]]:
    """
    Détermine quelles ressources l'utilisateur devrait donner
    si l'offre était acceptée.

    Si l'utilisateur est sender :

        il donne offered_resources.

    Si l'utilisateur est receiver :

        il doit fournir requested_resources.
    """

    if user.id == offer.sender_id:

        return [
            (
                resource.resource_type,
                resource.quantity
            )
            for resource in offer.offered_resources
        ]

    if user.id == offer.receiver_id:

        return [
            (
                resource.resource_type,
                resource.quantity
            )
            for resource in offer.requested_resources
        ]

    raise ValueError(
        "L'utilisateur ne participe pas à cette offre."
    )


def evaluate_offer_against_private_constraints(
    user: User,
    offer: Offer,
    partner_reputation: float | None = None
) -> PrivacyDecision:
    """
    Vérifie une offre en utilisant les données privées
    de l'utilisateur.

    La fonction retourne seulement une décision générique,
    et non les seuils privés exacts.
    """

    reasons: list[str] = []

    if user.id == offer.sender_id:
        partner_id = offer.receiver_id

    elif user.id == offer.receiver_id:
        partner_id = offer.sender_id

    else:
        return PrivacyDecision(
            allowed=False,
            reasons=[
                "user_not_participant"
            ]
        )

    if offer.is_expired():

        reasons.append(
            "offer_expired"
        )

    if not is_partner_allowed(
        user,
        partner_id,
        partner_reputation
    ):
        reasons.append(
            "partner_not_allowed"
        )

    resources_to_give = (
        _get_resources_given_by_user(
            user,
            offer
        )
    )

    for resource_type, quantity in resources_to_give:

        if not can_user_give(
            user,
            resource_type,
            quantity
        ):
            reasons.append(
                f"resource_constraint:{resource_type}"
            )

    return PrivacyDecision(
        allowed=len(reasons) == 0,
        reasons=reasons
    )


def get_negotiation_margin(
    user: User,
    resource_type: str,
    proposed_quantity: float
) -> MarginLevel:
    """
    Indique approximativement la marge restante.

    Exemple :

        Alice pourrait au maximum céder 20 STORAGE.

        proposition = 5
            -> HIGH

        proposition = 14
            -> MEDIUM

        proposition = 19
            -> LOW

        proposition = 25
            -> NONE

    L'agent obtient une catégorie, pas la limite exacte.
    """

    inventory = user.get_resource_quantity(
        resource_type
    )

    private_limit = (
        user.constraints
        .max_quantity_to_give
        .get(resource_type)
    )

    if private_limit is None:
        effective_limit = inventory
    else:
        effective_limit = min(
            inventory,
            private_limit
        )

    if effective_limit <= 0:
        return MarginLevel.NONE

    if proposed_quantity >= effective_limit:
        if proposed_quantity > effective_limit:
            return MarginLevel.NONE

        return MarginLevel.LOW

    remaining_ratio = (
        effective_limit - proposed_quantity
    ) / effective_limit

    if remaining_ratio >= 0.50:
        return MarginLevel.HIGH

    if remaining_ratio >= 0.20:
        return MarginLevel.MEDIUM

    return MarginLevel.LOW