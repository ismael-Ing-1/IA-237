# app/models/resource.py

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict, model_validator


class Resource(BaseModel):
    """
    Représente une ressource réellement possédée par un utilisateur.

    Exemples :
    - 10 GPU-hours de H100
    - 25 GPU-hours de A100
    - 500 GB de stockage
    - 100 CPU-hours
    """

    model_config = ConfigDict(validate_assignment=True)

    id: str = Field(default_factory=lambda: str(uuid4()))

    resource_type: str = Field(
        ...,
        min_length=1,
        description="Type de ressource : H100, A100, CPU, STORAGE..."
    )

    quantity: float = Field(
        ...,
        gt=0,
        description="Quantité disponible."
    )

    unit: str = Field(
        ...,
        min_length=1,
        description="Unité : gpu-hour, cpu-hour, GB/day..."
    )

    available_from: datetime | None = None
    available_until: datetime | None = None

    # Permet d'ajouter facilement des caractéristiques spécifiques.
    # Exemple :
    # {
    #     "vram_gb": 80,
    #     "region": "eu-west",
    #     "provider": "AWS"
    # }
    attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_availability_dates(self) -> "Resource":
        if (
            self.available_from is not None
            and self.available_until is not None
            and self.available_until <= self.available_from
        ):
            raise ValueError(
                "available_until doit être postérieur à available_from."
            )

        return self


class ResourceRequest(BaseModel):
    """
    Représente une ressource recherchée par un utilisateur.

    Exemple :
    Alice veut :
        8 H100 GPU-hours
        avant 18h
    """

    model_config = ConfigDict(validate_assignment=True)

    id: str = Field(default_factory=lambda: str(uuid4()))

    resource_type: str = Field(
        ...,
        min_length=1
    )

    quantity: float = Field(
        ...,
        gt=0
    )

    unit: str = Field(
        ...,
        min_length=1
    )

    deadline: datetime | None = None

    # Contraintes facultatives :
    # {
    #     "minimum_vram_gb": 80,
    #     "region": "eu-west"
    # }
    attributes: dict[str, Any] = Field(default_factory=dict)