# app/models/user.py

from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict

from app.models.resource import Resource, ResourceRequest


class NegotiationStrategy(str, Enum):
    """
    Style général de négociation de l'agent.
    """

    BALANCED = "balanced"
    CONSERVATIVE = "conservative"
    AGGRESSIVE = "aggressive"
    FAST = "fast"


class UserConstraints(BaseModel):
    """
    Contraintes privées que l'agent doit toujours respecter.

    Elles NE DOIVENT PAS être publiées sur le marketplace.
    """

    minimum_reputation: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0
    )

    max_negotiation_rounds: int = Field(
        default=10,
        ge=1
    )

    # Exemple :
    #
    # {
    #     "STORAGE": 20,
    #     "A100": 5
    # }
    #
    # signifie :
    # "ne jamais céder plus de 20 unités de STORAGE
    #  ou plus de 5 unités de A100."
    max_quantity_to_give: dict[str, float] = Field(
        default_factory=dict
    )

    require_human_approval: bool = True

    # Très important :
    # l'inventaire précis ne doit normalement pas être public.
    reveal_exact_inventory: bool = False

    additional_constraints: dict[str, Any] = Field(
        default_factory=dict
    )


class PublicUserProfile(BaseModel):
    """
    Informations qu'un autre agent a le droit de connaître.
    """

    user_id: str
    display_name: str

    offered_resource_types: list[str] = Field(
        default_factory=list
    )

    requested_resource_types: list[str] = Field(
        default_factory=list
    )

    online: bool = True


class User(BaseModel):
    """
    Représentation interne complète d'un utilisateur.

    Cette classe contient des informations privées.
    """

    model_config = ConfigDict(validate_assignment=True)

    id: str = Field(default_factory=lambda: str(uuid4()))

    name: str = Field(
        ...,
        min_length=1
    )

    # Ressources possédées
    resources: list[Resource] = Field(
        default_factory=list
    )

    # Ressources recherchées
    needs: list[ResourceRequest] = Field(
        default_factory=list
    )

    # Classement privé des partenaires préférés.
    # Exemple :
    # ["bob_id", "charlie_id", "david_id"]
    preferred_partners: list[str] = Field(
        default_factory=list
    )

    blocked_partners: list[str] = Field(
        default_factory=list
    )

    strategy: NegotiationStrategy = NegotiationStrategy.BALANCED

    constraints: UserConstraints = Field(
        default_factory=UserConstraints
    )

    online: bool = True

    def to_public_profile(self) -> PublicUserProfile:
        """
        Produit uniquement les informations que les autres agents
        sont autorisés à voir.
        """

        offered_types = sorted(
            set(resource.resource_type for resource in self.resources)
        )

        requested_types = sorted(
            set(request.resource_type for request in self.needs)
        )

        return PublicUserProfile(
            user_id=self.id,
            display_name=self.name,
            offered_resource_types=offered_types,
            requested_resource_types=requested_types,
            online=self.online
        )

    def get_resource_quantity(
        self,
        resource_type: str
    ) -> float:
        """
        Retourne la quantité totale possédée d'une ressource.
        """

        return sum(
            resource.quantity
            for resource in self.resources
            if resource.resource_type == resource_type
        )

    def prefers(
        self,
        user_a_id: str,
        user_b_id: str
    ) -> bool:
        """
        Renvoie True si user_a est préféré à user_b.

        Exemple :
        preferred_partners = [Bob, Charlie, David]

        prefers(Bob, David) -> True
        """

        try:
            rank_a = self.preferred_partners.index(user_a_id)
        except ValueError:
            rank_a = float("inf")

        try:
            rank_b = self.preferred_partners.index(user_b_id)
        except ValueError:
            rank_b = float("inf")

        return rank_a < rank_b