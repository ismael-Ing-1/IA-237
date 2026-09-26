# app/api/main.py

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# =========================
# MODELS
# =========================

from app.models.user import User
from app.models.resource import Resource, ResourceRequest
from app.models.negotiation import (
    Negotiation,
    NegotiationStatus,
)

# =========================
# MARKET
# =========================

from app.market.registry import MarketRegistry
from app.market.exchange import execute_exchange

# =========================
# TOOLS
# =========================

from app.tools.market_tools import (
    register_user,
    get_public_profile,
    search_providers,
    search_requesters,
)

from app.tools.negotiation_tools import (
    create_negotiation,
    send_offer,
    counter_offer,
    accept_offer,
    reject_offer,
    request_human_approval,
    approve_negotiation,
    reject_negotiation,
    cancel_negotiation,
)


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Compute Exchange Network API",
    description=(
        "API for a privacy-aware multi-agent marketplace "
        "for compute resources."
    ),
    version="0.1.0",
)


# ============================================================
# CORS
# ============================================================
#
# Pour le hackathon, on autorise tout.
#
# Plus tard, il faudra restreindre origins.
#

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# TEMPORARY IN-MEMORY STATE
# ============================================================
#
# Pour le MVP :
#
# users
# negotiations
# registry
#
# restent en mémoire.
#
# Plus tard :
#
# SQLite / PostgreSQL
#

registry = MarketRegistry()

users: dict[str, User] = {}

negotiations: dict[str, Negotiation] = {}


# ============================================================
# API REQUEST MODELS
# ============================================================


class CreateNegotiationRequest(BaseModel):
    """
    Requête permettant de créer une négociation.
    """

    participant_ids: list[str] = Field(
        ...,
        min_length=2,
    )

    max_rounds: int = Field(
        default=10,
        ge=1,
    )


class OfferRequest(BaseModel):
    """
    Corps HTTP permettant d'envoyer une offre.

    Exemple :

    Alice donne :
        10 STORAGE

    Alice demande :
        8 H100
    """

    sender_id: str
    receiver_id: str

    offered_resources: list[Resource]

    requested_resources: list[ResourceRequest]

    message: str | None = None

    expires_at: datetime | None = None


class CounterOfferRequest(OfferRequest):
    """
    Même structure qu'une OfferRequest,
    mais répond à une offre existante.
    """

    previous_offer_id: str


class RejectOfferRequest(BaseModel):
    """
    Permet de choisir si le refus ferme
    complètement la négociation.
    """

    close_negotiation: bool = False


# ============================================================
# HELPERS
# ============================================================


def get_user_or_404(
    user_id: str,
) -> User:
    """
    Récupère un utilisateur interne.

    ATTENTION :
    cette fonction est utilisée en interne uniquement.

    Elle ne doit pas servir à exposer les données privées.
    """

    user = users.get(user_id)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail=f"User '{user_id}' not found.",
        )

    return user


def get_negotiation_or_404(
    negotiation_id: str,
) -> Negotiation:

    negotiation = negotiations.get(
        negotiation_id
    )

    if negotiation is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Negotiation "
                f"'{negotiation_id}' not found."
            ),
        )

    return negotiation


def validate_participants_exist(
    participant_ids: list[str],
) -> None:

    missing_users = [
        user_id
        for user_id in participant_ids
        if user_id not in users
    ]

    if missing_users:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Some participants do not exist.",
                "missing_users": missing_users,
            },
        )


# ============================================================
# HEALTH
# ============================================================


@app.get("/health")
def health():
    """
    Vérifie simplement que l'API fonctionne.
    """

    return {
        "status": "ok",
        "users": len(users),
        "negotiations": len(negotiations),
    }


# ============================================================
# USERS
# ============================================================


@app.post(
    "/users",
    status_code=201,
)
def create_user(
    user: User,
):
    """
    Crée un utilisateur et l'enregistre
    automatiquement dans le marketplace.
    """

    if user.id in users:
        raise HTTPException(
            status_code=409,
            detail=(
                f"User '{user.id}' already exists."
            ),
        )

    users[user.id] = user

    try:
        register_user(
            registry,
            user,
        )

    except Exception as exc:

        # rollback simple
        users.pop(
            user.id,
            None,
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    # IMPORTANT :
    # on ne renvoie que le profil public.
    return user.to_public_profile()


@app.get("/users")
def list_users():
    """
    Retourne uniquement les profils publics.

    Les contraintes privées,
    préférences et inventaires précis
    ne sont pas exposés.
    """

    return [
        user.to_public_profile()
        for user in users.values()
    ]


@app.get("/users/{user_id}")
def read_user(
    user_id: str,
):
    """
    Retourne uniquement le profil PUBLIC
    d'un utilisateur.
    """

    profile = get_public_profile(
        registry,
        user_id,
    )

    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="User not found.",
        )

    return profile


# ============================================================
# MARKET
# ============================================================


@app.get(
    "/market/providers/{resource_type}"
)
def find_market_providers(
    resource_type: str,
    requester_id: str | None = None,
):
    """
    Trouve les utilisateurs proposant
    un type de ressource.

    Exemple :

        GET /market/providers/H100

    ou :

        GET /market/providers/H100
            ?requester_id=<alice-id>
    """

    blocked_ids: list[str] = []

    if requester_id is not None:

        requester = get_user_or_404(
            requester_id
        )

        blocked_ids = (
            requester.blocked_partners
        )

    return search_providers(
        registry=registry,
        resource_type=resource_type,
        requester_id=requester_id,
        blocked_ids=blocked_ids,
    )


@app.get(
    "/market/requesters/{resource_type}"
)
def find_market_requesters(
    resource_type: str,
    provider_id: str | None = None,
):
    """
    Trouve les utilisateurs recherchant
    une certaine ressource.
    """

    blocked_ids: list[str] = []

    if provider_id is not None:

        provider = get_user_or_404(
            provider_id
        )

        blocked_ids = (
            provider.blocked_partners
        )

    return search_requesters(
        registry=registry,
        resource_type=resource_type,
        provider_id=provider_id,
        blocked_ids=blocked_ids,
    )


# ============================================================
# NEGOTIATIONS
# ============================================================


@app.post(
    "/negotiations",
    status_code=201,
)
def start_negotiation(
    request: CreateNegotiationRequest,
):
    """
    Crée une nouvelle négociation.
    """

    validate_participants_exist(
        request.participant_ids
    )

    try:

        negotiation = create_negotiation(
            participant_ids=request.participant_ids,
            max_rounds=request.max_rounds,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    negotiations[
        negotiation.id
    ] = negotiation

    return negotiation


@app.get("/negotiations")
def list_negotiations():
    """
    Retourne toutes les négociations
    connues par l'API.
    """

    return list(
        negotiations.values()
    )


@app.get(
    "/negotiations/{negotiation_id}"
)
def read_negotiation(
    negotiation_id: str,
):
    """
    Retourne une négociation précise.
    """

    return get_negotiation_or_404(
        negotiation_id
    )


# ============================================================
# OFFERS
# ============================================================


@app.post(
    "/negotiations/{negotiation_id}/offers",
    status_code=201,
)
def create_offer(
    negotiation_id: str,
    request: OfferRequest,
):
    """
    Envoie une nouvelle offre.

    Exemple :

    Alice -> Bob

    10 STORAGE
        contre
    8 H100
    """

    negotiation = (
        get_negotiation_or_404(
            negotiation_id
        )
    )

    get_user_or_404(
        request.sender_id
    )

    get_user_or_404(
        request.receiver_id
    )

    try:

        offer = send_offer(
            negotiation=negotiation,

            sender_id=request.sender_id,
            receiver_id=request.receiver_id,

            offered_resources=(
                request.offered_resources
            ),

            requested_resources=(
                request.requested_resources
            ),

            message=request.message,

            expires_at=request.expires_at,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    return offer


# ============================================================
# COUNTER OFFERS
# ============================================================


@app.post(
    "/negotiations/"
    "{negotiation_id}/counter-offers",
    status_code=201,
)
def create_counter_offer(
    negotiation_id: str,
    request: CounterOfferRequest,
):
    """
    Envoie une contre-offre.

    Exemple :

    Alice :
        10 STORAGE

    Bob :
        15 STORAGE

    Alice :
        12 STORAGE
    """

    negotiation = (
        get_negotiation_or_404(
            negotiation_id
        )
    )

    get_user_or_404(
        request.sender_id
    )

    get_user_or_404(
        request.receiver_id
    )

    try:

        offer = counter_offer(
            negotiation=negotiation,

            previous_offer_id=(
                request.previous_offer_id
            ),

            sender_id=request.sender_id,
            receiver_id=request.receiver_id,

            offered_resources=(
                request.offered_resources
            ),

            requested_resources=(
                request.requested_resources
            ),

            message=request.message,

            expires_at=request.expires_at,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    return offer


# ============================================================
# ACCEPT OFFER
# ============================================================


@app.post(
    "/negotiations/"
    "{negotiation_id}/offers/"
    "{offer_id}/accept"
)
def accept_negotiation_offer(
    negotiation_id: str,
    offer_id: str,
):
    """
    Les agents considèrent qu'un accord
    a été trouvé.

    Attention :

    ce n'est PAS encore la validation humaine.
    """

    negotiation = (
        get_negotiation_or_404(
            negotiation_id
        )
    )

    try:

        offer = accept_offer(
            negotiation,
            offer_id,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    return {
        "message": "Offer accepted by agents.",
        "offer": offer,
        "negotiation_status": (
            negotiation.status
        ),
    }


# ============================================================
# REJECT OFFER
# ============================================================


@app.post(
    "/negotiations/"
    "{negotiation_id}/offers/"
    "{offer_id}/reject"
)
def reject_negotiation_offer(
    negotiation_id: str,
    offer_id: str,
    request: RejectOfferRequest | None = None,
):
    """
    Refuse une offre.

    La négociation peut continuer,
    sauf si close_negotiation=true.
    """

    negotiation = (
        get_negotiation_or_404(
            negotiation_id
        )
    )

    close_negotiation = False

    if request is not None:
        close_negotiation = (
            request.close_negotiation
        )

    try:

        offer = reject_offer(
            negotiation,
            offer_id,
            close_negotiation=close_negotiation,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    return {
        "message": "Offer rejected.",
        "offer": offer,
        "negotiation_status": (
            negotiation.status
        ),
    }


# ============================================================
# HUMAN-IN-THE-LOOP
# ============================================================


@app.post(
    "/negotiations/"
    "{negotiation_id}/request-approval"
)
def ask_human_approval(
    negotiation_id: str,
):
    """
    Demande la validation humaine
    après qu'un accord entre agents
    a été trouvé.
    """

    negotiation = (
        get_negotiation_or_404(
            negotiation_id
        )
    )

    try:

        request_human_approval(
            negotiation
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    return {
        "message": (
            "Negotiation is waiting "
            "for human approval."
        ),
        "negotiation": negotiation,
    }


@app.post(
    "/negotiations/{negotiation_id}/approve"
)
def approve_deal(
    negotiation_id: str,
):
    """
    L'utilisateur humain approuve le deal.

    Cela ne l'exécute pas encore.
    """

    negotiation = (
        get_negotiation_or_404(
            negotiation_id
        )
    )

    try:

        approve_negotiation(
            negotiation
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    return {
        "message": (
            "Negotiation approved by human."
        ),
        "negotiation": negotiation,
    }


@app.post(
    "/negotiations/{negotiation_id}/reject"
)
def human_reject_deal(
    negotiation_id: str,
):
    """
    L'utilisateur humain refuse
    le deal proposé.
    """

    negotiation = (
        get_negotiation_or_404(
            negotiation_id
        )
    )

    reject_negotiation(
        negotiation
    )

    return {
        "message": (
            "Negotiation rejected by human."
        ),
        "negotiation": negotiation,
    }


# ============================================================
# CANCEL
# ============================================================


@app.post(
    "/negotiations/{negotiation_id}/cancel"
)
def cancel_deal(
    negotiation_id: str,
):
    """
    Annule manuellement une négociation.
    """

    negotiation = (
        get_negotiation_or_404(
            negotiation_id
        )
    )

    cancel_negotiation(
        negotiation
    )

    return {
        "message": "Negotiation cancelled.",
        "negotiation": negotiation,
    }


# ============================================================
# EXECUTE EXCHANGE
# ============================================================


@app.post(
    "/negotiations/{negotiation_id}/execute"
)
def execute_approved_deal(
    negotiation_id: str,
):
    """
    Exécute réellement l'échange.

    Workflow attendu :

        AGREEMENT_FOUND
                ↓
        WAITING_HUMAN
                ↓
           APPROVED
                ↓
           EXECUTE
    """

    negotiation = (
        get_negotiation_or_404(
            negotiation_id
        )
    )

    if (
        negotiation.status
        != NegotiationStatus.APPROVED
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Negotiation must be approved "
                "before execution."
            ),
        )

    try:

        result = execute_exchange(
            negotiation,
            users,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Exchange execution failed: "
                f"{exc}"
            ),
        )

    if result is not True:

        raise HTTPException(
            status_code=500,
            detail=(
                "Exchange engine did not "
                "confirm the transaction."
            ),
        )

    return {
        "success": True,
        "message": "Exchange executed.",
        "negotiation_id": negotiation.id,
    }


# ============================================================
# DEV / HACKATHON UTILITY
# ============================================================


@app.delete("/dev/reset")
def reset_state():
    """
    Utilitaire de développement.

    Supprime l'état en mémoire de l'API.

    À retirer en production.
    """

    global registry

    users.clear()
    negotiations.clear()

    registry = MarketRegistry()

    return {
        "message": "Application state reset."
    }