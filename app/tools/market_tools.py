# app/tools/market_tools.py

from __future__ import annotations

from typing import Any

from app.models.user import User, PublicUserProfile

from app.models.resource import Resource


def register_user(
    registry: Any,
    user: User
) -> None:
    """
    Enregistre un utilisateur dans le marketplace.

    Le registry est volontairement typé Any afin de ne pas
    coupler ce module à l'implémentation concrète de MarketRegistry.

    Le registry doit simplement implémenter :

        register_user(user: User) -> None
    """

    registry.register_user(user)


def get_public_profile(
    registry: Any,
    user_id: str
) -> PublicUserProfile | None:
    """
    Récupère uniquement le profil PUBLIC d'un utilisateur.

    Les informations privées comme :
    - inventaire exact
    - préférences
    - limites de négociation

    ne doivent jamais être retournées par cette fonction.
    """

    return registry.get_public_profile(user_id)


def search_providers(
    registry: Any,
    resource_type: str,
    requester_id: str | None = None,
    blocked_ids: list[str] | None = None
) -> list[PublicUserProfile]:
    """
    Recherche les utilisateurs proposant un certain type
    de ressource.

    Exemple :

        search_providers(
            registry,
            "H100",
            requester_id=alice.id
        )

    peut retourner Bob et Charlie.

    requester_id permet d'éviter de retourner l'utilisateur
    lui-même.

    blocked_ids permet d'exclure certains partenaires.
    """

    providers = registry.find_providers(resource_type)

    blocked = set(blocked_ids or [])

    results: list[PublicUserProfile] = []

    for provider in providers:

        if not provider.online:
            continue

        if (
            requester_id is not None
            and provider.user_id == requester_id
        ):
            continue

        if provider.user_id in blocked:
            continue

        results.append(provider)

    return results


def search_requesters(
    registry: Any,
    resource_type: str,
    provider_id: str | None = None,
    blocked_ids: list[str] | None = None
) -> list[PublicUserProfile]:
    """
    Recherche les utilisateurs actuellement intéressés
    par un certain type de ressource.

    Exemple :

        search_requesters(
            registry,
            "STORAGE"
        )

    retourne les utilisateurs recherchant du STORAGE.
    """

    requesters = registry.find_requesters(resource_type)

    blocked = set(blocked_ids or [])

    results: list[PublicUserProfile] = []

    for requester in requesters:

        if not requester.online:
            continue

        if (
            provider_id is not None
            and requester.user_id == provider_id
        ):
            continue

        if requester.user_id in blocked:
            continue

        results.append(requester)

    return results

def add_user_resource(
    registry: Any,
    user_id: str,
    resource: Resource
) -> Resource:
    """
    Ajoute une nouvelle ressource à un utilisateur.
    """

    return registry.add_user_resource(
        user_id=user_id,
        resource=resource
    )


def increase_user_resource(
    registry: Any,
    user_id: str,
    resource_id: str,
    amount: float
) -> Resource:
    """
    Augmente une ressource existante.
    """

    return registry.increase_user_resource(
        user_id=user_id,
        resource_id=resource_id,
        amount=amount
    )


def decrease_user_resource(
    registry: Any,
    user_id: str,
    resource_id: str,
    amount: float
) -> Resource | None:
    """
    Diminue une ressource existante.
    """

    return registry.decrease_user_resource(
        user_id=user_id,
        resource_id=resource_id,
        amount=amount
    )


def set_user_resource_quantity(
    registry: Any,
    user_id: str,
    resource_id: str,
    quantity: float
) -> Resource | None:
    """
    Remplace la quantité existante par une nouvelle valeur.
    """

    return registry.set_user_resource_quantity(
        user_id=user_id,
        resource_id=resource_id,
        quantity=quantity
    )