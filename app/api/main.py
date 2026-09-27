"""API du simulateur local : REST (commandes/état) + WebSocket (observations).

Une instance en mémoire et un worker Uvicorn. Mode opérateur de hackathon,
pas une application multi-utilisateurs authentifiée : voir docs/REALTIME.md.
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from itertools import count

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.agents.orchestrator import AgentConflict, AgentOrchestrator, RUNNABLE
from app.agents.personal_agent import AgentStepResult, PersonalAgent
from app.api.websocket import WebSocketHub
from app.market.registry import MarketRegistry
from app.llm import build_llm_policy
from app.models.negotiation import Negotiation, NegotiationStatus
from app.models.offer import Offer, OfferStatus
from app.models.resource import Resource, ResourceRequest
from app.models.user import NegotiationStrategy, User
from app.privacy import PrivacyAction, PrivacyGuard
from app.reputation.reputation import ReputationEventType, ReputationManager
from app.simulation import MarketEvent, SimulationWorld
from app.simulation.scenario_loader import (
    apply_prepared_scenario, list_scenarios, load_scenario, prepare_scenario,
)
from app.tools.market_tools import get_public_profile, search_providers, search_requesters
from app.tools.negotiation_tools import (
    accept_offer, approve_negotiation, cancel_negotiation, counter_offer,
    create_negotiation, reject_negotiation, reject_offer, request_human_approval, send_offer,
)

logger = logging.getLogger(__name__)
ALLOWED_ORIGINS = [x.strip() for x in os.getenv(
    "DEMO_ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173",
).split(",") if x.strip()]
ENABLE_DEMO_ROUTES = os.getenv("ENABLE_DEMO_ROUTES", "1") == "1"

# Une SEULE création du monde. Les mêmes services sont injectés partout.
world = SimulationWorld()
reputation = ReputationManager()
privacy_guard = PrivacyGuard()
personal_agents: dict[str, PersonalAgent] = {}
world_lock = asyncio.Lock()
maintenance_lock = asyncio.Lock()
websocket_hub = WebSocketHub()
llm_policy = build_llm_policy()
orchestrator = AgentOrchestrator(
    world=world,
    reputation=reputation,
    privacy_guard=privacy_guard,
    personal_agents=personal_agents,
    emit_event=websocket_hub.emit,
    llm_policy=llm_policy,
    lock=world_lock,
    step_delay=float(
        os.getenv(
            "AGENT_STEP_DELAY_SECONDS",
            "0.65",
        )
    ),
)


@asynccontextmanager
async def lifespan(application: FastAPI):
    orchestrator.maintenance = False
    try:
        yield
    finally:
        orchestrator.maintenance = True
        await orchestrator.stop_all()
        await websocket_hub.shutdown()


app = FastAPI(title="Compute Exchange Network API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"], allow_headers=["Content-Type"],
)
app.state.world = world
app.state.reputation = reputation
app.state.privacy_guard = privacy_guard
app.state.personal_agents = personal_agents
app.state.websocket_hub = websocket_hub
app.state.llm_policy = llm_policy
app.state.orchestrator = orchestrator


@app.exception_handler(AgentConflict)
async def conflict_handler(request: Request, exc: AgentConflict):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(ValueError)
async def value_handler(request: Request, exc: ValueError):
    # Les détails complets ne sont pas diffusés au flux public d'activité.
    logger.warning("Operation rejected at %s: %s", request.url.path, exc)
    return JSONResponse(status_code=400, content={
        "detail": "Operation rejected: invalid terms, state or private policy. See the backend logs.",
    })


class CreateNegotiationRequest(BaseModel):
    participant_ids: list[str] = Field(min_length=2, max_length=2)
    max_rounds: int = Field(default=10, ge=1, le=100)


class OfferRequest(BaseModel):
    sender_id: str
    receiver_id: str
    offered_resources: list[Resource] = Field(min_length=1)
    requested_resources: list[ResourceRequest] = Field(min_length=1)
    message: str | None = None
    expires_at: datetime | None = None


class CounterOfferRequest(OfferRequest):
    previous_offer_id: str


class RejectOfferRequest(BaseModel):
    close_negotiation: bool = False


class AdvanceTimeRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    seconds: float = Field(default=0, ge=0)
    minutes: float = Field(default=0, ge=0)
    hours: float = Field(default=0, ge=0)
    days: float = Field(default=0, ge=0)


class RunUntilRequest(BaseModel):
    target_time: datetime


class PursueAgentRequest(BaseModel):
    request: ResourceRequest
    offered_resources: list[Resource] = Field(min_length=1)
    message: str | None = None


class HumanRejectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    continue_search: bool = True


class CoalitionHumanDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str


class HandleOfferRequest(BaseModel):
    negotiation_id: str
    offer_id: str


class UpdateStrategyRequest(BaseModel):
    """Modifie la politique de négociation d'un PersonalAgent."""

    strategy: NegotiationStrategy


def get_user_or_404(user_id: str) -> User:
    user = world.get_user(user_id)
    if user is None:
        raise HTTPException(404, "User not found.")
    return user


def get_negotiation_or_404(negotiation_id: str) -> Negotiation:
    negotiation = world.get_negotiation(negotiation_id)
    if negotiation is None:
        raise HTTPException(404, "Negotiation not found.")
    return negotiation


def get_personal_agent(user_id: str) -> PersonalAgent:
    get_user_or_404(user_id)
    return orchestrator.get_personal_agent(user_id)


def ensure_mutable(negotiation_id: str | None = None, *, allow_worker: bool = False) -> None:
    if orchestrator.maintenance:
        raise AgentConflict("Simulator maintenance is in progress.")
    if negotiation_id is not None:
        if negotiation_id not in world.active_negotiations:
            raise AgentConflict("This negotiation is already executed or no longer active.")
        if not allow_worker and orchestrator.is_running(negotiation_id):
            raise AgentConflict("Automatic agent processing is in progress.")


def ensure_pending_offer(negotiation: Negotiation, offer_id: str) -> Offer:
    if negotiation.status not in RUNNABLE:
        raise AgentConflict("Negotiation is no longer open to offers.")
    offer = negotiation.get_last_offer()
    if offer is None or offer.id != offer_id or offer.status != OfferStatus.PENDING:
        raise AgentConflict("Only the latest pending offer may be modified.")
    if offer.is_expired():
        raise AgentConflict("The latest offer has expired.")
    return offer


def safe_manual_offer(negotiation: Negotiation, request: OfferRequest) -> Offer:
    """Les endpoints manuels passent eux aussi par la politique de l'émetteur."""
    if negotiation.status not in RUNNABLE:
        raise AgentConflict("Negotiation is no longer accepting offers.")
    if len(negotiation.participant_ids) != 2 or set(negotiation.participant_ids) != {
        request.sender_id, request.receiver_id,
    }:
        raise ValueError("Invalid bilateral offer participants.")
    sender = get_user_or_404(request.sender_id)
    receiver = get_user_or_404(request.receiver_id)
    if not receiver.online:
        raise ValueError("Receiver offline.")
    orchestrator.validate_outgoing(sender.id, request.offered_resources)
    message = None if request.message is None else privacy_guard.sanitize_message(sender, request.message)
    preview = Offer(
        sender_id=sender.id, receiver_id=receiver.id,
        offered_resources=request.offered_resources, requested_resources=request.requested_resources,
        message=message, expires_at=request.expires_at,
    )
    if preview.is_expired():
        raise ValueError("Offer already expired.")
    check = privacy_guard.check_offer(sender, preview, partner_reputation=reputation.get_score(receiver.id))
    if check.action == PrivacyAction.BLOCK:
        raise ValueError("Manual offer blocked by private policy.")
    return preview


def simulation_snapshot() -> dict:
    # Profil public uniquement. Les inventaires complets ne partent pas dans ce champ users.
    return {
        "current_time": world.current_time,
        "users": [user.to_public_profile() for user in world.get_users()],
        "active_negotiations": world.get_active_negotiations(),
        "completed_negotiations": list(world.completed_negotiations.values()),
        "scheduled_events": world.get_scheduled_events(),
        "event_history": world.event_history,
        "coalitions": orchestrator.coalition_snapshot(),
        "coalition_deals": orchestrator.coalition_deal_snapshot(),
        "agent_states": orchestrator.runtime_snapshot(),
    }


async def changed() -> None:
    # L'ancien frontend invalide son snapshot sur market_updated.
    await websocket_hub.emit(event_type="market_updated", payload={"message": "REST state changed."})


async def negotiation_event(kind: str, negotiation: Negotiation, *, offer: Offer | None = None) -> None:
    payload = {"negotiation_id": negotiation.id, "negotiation": negotiation}
    if offer is not None:
        payload["offer"] = offer
    await websocket_hub.emit(event_type=kind, entity_id=negotiation.id, payload=payload)
    await changed()


# ---- WebSocket / health ------------------------------------------------------
@app.websocket("/ws")
async def realtime_websocket(websocket: WebSocket):
    # CORS ne protège pas un WebSocket. Le contrôle d'Origin est explicite.
    origin = websocket.headers.get("origin")
    if origin is not None and origin not in ALLOWED_ORIGINS:
        await websocket.close(code=1008)
        return
    await websocket_hub.serve(websocket)


@app.get("/health")
async def health():
    async with world_lock:
        return {
            "status": "ok", "users": len(world.users),
            "negotiations": len(world.active_negotiations) + len(world.completed_negotiations),
            "active_negotiations": len(world.active_negotiations),
            "completed_negotiations": len(world.completed_negotiations),
            "scheduled_events": len(world.get_scheduled_events()),
            "current_time": world.current_time,
            "websocket_clients": websocket_hub.connection_count,
            "running_agent_tasks": orchestrator.running_count,
            "coalition_deals": len(orchestrator.coalition_deal_snapshot()),
        }


@app.get("/llm/status")
async def llm_status():
    """Safe operational status; never returns the API key."""
    return llm_policy.status()


# ---- Users / market ---------------------------------------------------------
@app.post("/users", status_code=201)
async def create_user(user: User):
    async with world_lock:
        ensure_mutable()
        if world.get_user(user.id) is not None:
            raise HTTPException(409, "User already exists.")
        world.add_user(user)
        reputation.register_user(user.id)
        await changed()
        return user.to_public_profile()


@app.get("/users")
async def list_users():
    async with world_lock:
        return [user.to_public_profile() for user in world.get_users()]


@app.get("/users/{user_id}")
async def read_user(user_id: str):
    async with world_lock:
        profile = get_public_profile(world.registry, user_id)
        if profile is None:
            raise HTTPException(404, "User not found.")
        return profile


@app.get("/users/{user_id}/dashboard")
async def user_dashboard_state(user_id: str):
    # Vue opérateur locale. Ne pas déployer publiquement sans authentification/autorisation.
    async with world_lock:
        user = get_user_or_404(user_id)
        return {
            "id": user.id, "name": user.name, "online": user.online,
            "resources": user.resources, "needs": user.needs, "strategy": user.strategy,
        }


@app.patch("/users/{user_id}/strategy")
async def update_user_strategy(
    user_id: str,
    request: UpdateStrategyRequest,
):
    """
    Change la stratégie d'un utilisateur.

    Le PersonalAgent ne conserve pas une copie de la stratégie :
    il lit self.user.strategy à chaque décision. La modification
    s'applique donc aux prochaines décisions sans recréer l'agent.
    """
    async with world_lock:
        ensure_mutable()

        user = get_user_or_404(user_id)
        previous = user.strategy
        user.strategy = request.strategy

        await websocket_hub.emit(
            event_type="market_updated",
            user_id=user.id,
            entity_id=user.id,
            payload={
                "message": (
                    f"{user.name} changed agent strategy "
                    f"from {previous.value} to {user.strategy.value}."
                ),
                "strategy": user.strategy.value,
                "previous_strategy": previous.value,
            },
        )

        return {
            "user_id": user.id,
            "strategy": user.strategy,
        }


@app.get("/market/providers/{resource_type}")
async def find_market_providers(resource_type: str, requester_id: str | None = None):
    async with world_lock:
        blocked = [] if requester_id is None else get_user_or_404(requester_id).blocked_partners
        return search_providers(registry=world.registry, resource_type=resource_type, requester_id=requester_id, blocked_ids=blocked)


@app.get("/market/requesters/{resource_type}")
async def find_market_requesters(resource_type: str, provider_id: str | None = None):
    async with world_lock:
        blocked = [] if provider_id is None else get_user_or_404(provider_id).blocked_partners
        return search_requesters(registry=world.registry, resource_type=resource_type, provider_id=provider_id, blocked_ids=blocked)


# ---- Agents -----------------------------------------------------------------
@app.post("/agents/{user_id}/pursue", response_model=AgentStepResult)
async def pursue_agent_request(user_id: str, request: PursueAgentRequest):
    get_user_or_404(user_id)
    return await orchestrator.pursue(
        user_id=user_id, request=request.request,
        offered_resources=request.offered_resources, message=request.message,
    )


@app.get("/agents/{user_id}/candidates")
async def discover_agent_candidates(user_id: str, resource_type: str):
    async with world_lock:
        return get_personal_agent(user_id).discover_candidates(resource_type)


@app.post("/agents/{user_id}/handle-offer", response_model=AgentStepResult)
async def handle_agent_offer(user_id: str, request: HandleOfferRequest):
    get_user_or_404(user_id)
    get_negotiation_or_404(request.negotiation_id)
    return await orchestrator.handle_offer_once(
        user_id=user_id, negotiation_id=request.negotiation_id, offer_id=request.offer_id,
    )


@app.post("/negotiations/{negotiation_id}/resume", response_model=AgentStepResult)
async def resume_negotiation(negotiation_id: str):
    get_negotiation_or_404(negotiation_id)
    return await orchestrator.resume(negotiation_id)


@app.get("/coalitions/{user_id}")
async def discover_coalitions(
    user_id: str, min_size: int = Query(default=3, ge=3, le=6),
    max_size: int = Query(default=4, ge=3, le=6),
):
    async with world_lock:
        get_user_or_404(user_id)
        return orchestrator.discover_coalitions(user_id, min_size, max_size)


@app.get("/coalition-deals")
async def list_coalition_deals():
    async with world_lock:
        return orchestrator.coalition_deal_snapshot()


@app.get("/coalition-deals/{coalition_id}")
async def read_coalition_deal(coalition_id: str):
    async with world_lock:
        try:
            return orchestrator.get_coalition_deal(coalition_id)
        except ValueError as exc:
            raise HTTPException(404, "Coalition deal not found.") from exc


@app.post("/coalition-deals/{coalition_id}/approve")
async def approve_coalition_deal(
    coalition_id: str,
    request: CoalitionHumanDecisionRequest,
):
    # Orchestrator acquires the shared world lock itself.
    get_user_or_404(request.user_id)
    return await orchestrator.approve_coalition_by_human(
        coalition_id,
        request.user_id,
    )


@app.post("/coalition-deals/{coalition_id}/reject")
async def reject_coalition_deal(
    coalition_id: str,
    request: CoalitionHumanDecisionRequest,
):
    # Rejecting one proposal never partially executes it. The owner
    # objective may continue to the next coalition candidate.
    get_user_or_404(request.user_id)
    return await orchestrator.reject_coalition_by_human(
        coalition_id,
        request.user_id,
    )


@app.post("/coalition-deals/{coalition_id}/execute")
async def execute_coalition_deal(coalition_id: str):
    # Explicit execution remains separate from every human approval.
    try:
        return await orchestrator.execute_coalition(coalition_id)
    except AgentConflict:
        raise
    except Exception as exc:
        logger.exception("Atomic coalition execution failed")
        raise HTTPException(
            500,
            "Atomic coalition execution failed. No partial transfers were committed.",
        ) from exc


@app.post("/negotiations/{negotiation_id}/mediate")
async def mediate_negotiation(negotiation_id: str):
    async with world_lock:
        ensure_mutable(negotiation_id)
        return await orchestrator.mediate_negotiation(get_negotiation_or_404(negotiation_id))


# ---- Negotiations / offers : chemins HTTP conservés --------------------------
@app.post("/negotiations", status_code=201)
async def start_negotiation(request: CreateNegotiationRequest):
    async with world_lock:
        ensure_mutable()
        if len(set(request.participant_ids)) != 2:
            raise ValueError("Two distinct participants required.")
        for user_id in request.participant_ids:
            get_user_or_404(user_id)
        negotiation = create_negotiation(request.participant_ids, request.max_rounds)
        world.add_negotiation(negotiation)
        await negotiation_event("negotiation_started", negotiation)
        return negotiation


@app.get("/negotiations")
async def list_negotiations():
    async with world_lock:
        return [*world.active_negotiations.values(), *world.completed_negotiations.values()]


@app.get("/negotiations/{negotiation_id}")
async def read_negotiation(negotiation_id: str):
    async with world_lock:
        return get_negotiation_or_404(negotiation_id)


@app.post("/negotiations/{negotiation_id}/offers", status_code=201)
async def create_offer(negotiation_id: str, request: OfferRequest):
    async with world_lock:
        ensure_mutable(negotiation_id)
        negotiation = get_negotiation_or_404(negotiation_id)
        preview = safe_manual_offer(negotiation, request)
        offer = send_offer(
            negotiation=negotiation, sender_id=preview.sender_id, receiver_id=preview.receiver_id,
            offered_resources=preview.offered_resources, requested_resources=preview.requested_resources,
            message=preview.message, expires_at=preview.expires_at,
        )
        await negotiation_event("offer_sent", negotiation, offer=offer)
        return offer


@app.post("/negotiations/{negotiation_id}/counter-offers", status_code=201)
async def create_counter_offer(negotiation_id: str, request: CounterOfferRequest):
    async with world_lock:
        ensure_mutable(negotiation_id)
        negotiation = get_negotiation_or_404(negotiation_id)
        previous = ensure_pending_offer(negotiation, request.previous_offer_id)
        if request.sender_id != previous.receiver_id or request.receiver_id != previous.sender_id:
            raise ValueError("A counter-offer must reverse sender and receiver.")
        preview = safe_manual_offer(negotiation, request)
        offer = counter_offer(
            negotiation=negotiation, previous_offer_id=previous.id,
            sender_id=preview.sender_id, receiver_id=preview.receiver_id,
            offered_resources=preview.offered_resources, requested_resources=preview.requested_resources,
            message=preview.message, expires_at=preview.expires_at,
        )
        await negotiation_event("counter_offer_sent", negotiation, offer=offer)
        return offer


@app.post("/negotiations/{negotiation_id}/offers/{offer_id}/accept")
async def accept_negotiation_offer(negotiation_id: str, offer_id: str):
    async with world_lock:
        ensure_mutable(negotiation_id)
        negotiation = get_negotiation_or_404(negotiation_id)
        ensure_pending_offer(negotiation, offer_id)
        # Vérifier l'accord sur une copie avant de muter l'état live.
        preview = negotiation.model_copy(deep=True)
        accept_offer(preview, offer_id)
        orchestrator.validate_settlement(preview)
        offer = accept_offer(negotiation, offer_id)
        await negotiation_event("offer_accepted", negotiation, offer=offer)
        return {"message": "Offer accepted by agents.", "offer": offer,
                "negotiation_status": negotiation.status}


@app.post("/negotiations/{negotiation_id}/offers/{offer_id}/reject")
async def reject_negotiation_offer(
    negotiation_id: str, offer_id: str, request: RejectOfferRequest | None = None,
):
    async with world_lock:
        ensure_mutable(negotiation_id)
        negotiation = get_negotiation_or_404(negotiation_id)
        ensure_pending_offer(negotiation, offer_id)
        offer = reject_offer(negotiation, offer_id, close_negotiation=bool(request and request.close_negotiation))
        await negotiation_event("offer_rejected", negotiation, offer=offer)
        return {"message": "Offer rejected.", "offer": offer, "negotiation_status": negotiation.status}


# ---- Human-in-the-loop : aucune exécution ni approbation par le WS ------------
@app.post("/negotiations/{negotiation_id}/request-approval")
async def ask_human_approval(negotiation_id: str):
    async with world_lock:
        ensure_mutable(negotiation_id)
        negotiation = get_negotiation_or_404(negotiation_id)
        if negotiation.status != NegotiationStatus.AGREEMENT_FOUND:
            raise AgentConflict("No new agreement awaiting an approval request.")
        request_human_approval(negotiation)
        await negotiation_event("human_approval_required", negotiation)
        return {"message": "Negotiation is waiting for human approval.", "negotiation": negotiation}


@app.post("/negotiations/{negotiation_id}/approve")
async def approve_deal(negotiation_id: str):
    async with world_lock:
        ensure_mutable(negotiation_id)
        negotiation = get_negotiation_or_404(negotiation_id)
        if negotiation.status != NegotiationStatus.WAITING_HUMAN:
            raise AgentConflict("Negotiation is not awaiting human approval.")
        orchestrator.validate_settlement(negotiation)
        approve_negotiation(negotiation)
        orchestrator.mark_deal_state(negotiation_id, "approved")
        await negotiation_event("human_approved", negotiation)
        return {"message": "Negotiation approved by human.", "negotiation": negotiation}


@app.post("/negotiations/{negotiation_id}/reject")
async def human_reject_deal(negotiation_id: str, request: HumanRejectionRequest | None = None):
    get_negotiation_or_404(negotiation_id)
    return await orchestrator.reject_by_human(
        negotiation_id, continue_search=request.continue_search if request else True,
    )


@app.post("/agents/{user_id}/stop")
async def stop_agent_objective(user_id: str):
    get_user_or_404(user_id)
    return await orchestrator.stop_user(user_id)


@app.get("/agents/{user_id}/state")
async def agent_runtime_state(user_id: str):
    async with world_lock:
        get_user_or_404(user_id)
        return next((state for state in orchestrator.runtime_snapshot() if state["user_id"] == user_id),
                    {"user_id": user_id, "status": "idle", "reason": "No active objective.",
                     "negotiation_id": None, "objective_id": None, "updated_at": None})


@app.post("/negotiations/{negotiation_id}/cancel")
async def cancel_deal(negotiation_id: str):
    async with world_lock:
        ensure_mutable(negotiation_id, allow_worker=True)
        negotiation = get_negotiation_or_404(negotiation_id)
        cancel_negotiation(negotiation)
        orchestrator.mark_deal_state(negotiation_id, "cancelled")
        await negotiation_event("negotiation_updated", negotiation)
        return {"message": "Negotiation cancelled.", "negotiation": negotiation}


@app.post("/negotiations/{negotiation_id}/execute")
async def execute_approved_deal(negotiation_id: str):
    async with world_lock:
        negotiation = get_negotiation_or_404(negotiation_id)
        ensure_mutable(negotiation_id)  # Empêche une seconde exécution après archivage.
        if negotiation.status != NegotiationStatus.APPROVED:
            raise AgentConflict("Human approval is required before execution.")
        orchestrator.validate_settlement(negotiation)
        await negotiation_event("exchange_started", negotiation)
        try:
            success = world.execute_negotiation(negotiation_id)
            if success is not True:
                raise RuntimeError("Settlement engine did not confirm success.")
        except Exception as exc:
            logger.exception("Exchange engine failed")
            await websocket_hub.emit(
                event_type="exchange_failed", entity_id=negotiation_id,
                payload={"message": "Exchange engine failed. Inspect server logs before retrying."},
            )
            raise HTTPException(500, "Exchange failed. Inspect server logs before retrying.") from exc
        # Enregistrer uniquement une transaction réussie, pas un délai inventé.
        for user_id in set(negotiation.participant_ids):
            reputation.record_event(user_id, ReputationEventType.TRANSACTION_SUCCESS)
        orchestrator.mark_deal_state(negotiation_id, "completed")
        await negotiation_event("exchange_completed", negotiation)
        return {"success": True, "message": "Exchange executed.", "negotiation_id": negotiation_id}


# ---- Simulation -------------------------------------------------------------
@app.get("/simulation/state")
async def simulation_state():
    async with world_lock:
        return simulation_snapshot()


@app.get("/simulation/events")
async def list_scheduled_events():
    async with world_lock:
        return world.get_scheduled_events()


@app.get("/simulation/history")
async def simulation_history():
    async with world_lock:
        return world.event_history


@app.post("/simulation/events", status_code=201)
async def schedule_simulation_event(event: MarketEvent):
    async with world_lock:
        ensure_mutable()
        get_user_or_404(event.user_id)
        world.schedule_event(event)
        # Le flux partagé n'expose ni la ressource privée exacte ni les metadata brutes.
        await websocket_hub.emit(event_type="market_event_scheduled", user_id=event.user_id, payload={
            "event_id": event.id, "event_type": event.event_type, "scheduled_at": event.scheduled_at,
            "message": "A simulation event was scheduled.",
        })
        await changed()
        return event


async def emit_simulation_results(executions) -> None:
    for execution in executions:
        await websocket_hub.emit(event_type="market_event_executed", user_id=execution.user_id, payload={
            "event_id": execution.event_id, "event_type": execution.event_type,
            "executed_at": execution.executed_at, "success": execution.success,
            "message": "Simulation event executed." if execution.success else "Simulation event failed.",
        })
    await websocket_hub.emit(event_type="simulation_time_updated", payload={"current_time": world.current_time})
    await changed()


@app.post("/simulation/advance")
async def advance_simulation_time(request: AdvanceTimeRequest):
    async with world_lock:
        ensure_mutable()
        executions = world.advance_time(**request.model_dump())
        await emit_simulation_results(executions)
        return {"current_time": world.current_time, "executed_events": executions,
                "scheduled_events": world.get_scheduled_events()}


@app.post("/simulation/run-until")
async def run_simulation_until(request: RunUntilRequest):
    async with world_lock:
        ensure_mutable()
        executions = world.run_until(request.target_time)
        await emit_simulation_results(executions)
        return {"current_time": world.current_time, "executed_events": executions,
                "scheduled_events": world.get_scheduled_events()}


# ---- Chargement explicite des scénarios (opérations destructives de démo) ------
def require_demo_routes() -> None:
    if not ENABLE_DEMO_ROUTES:
        raise HTTPException(404, "Demo endpoints disabled.")


@app.get("/dev/scenarios")
async def available_scenarios():
    require_demo_routes()
    return {"scenarios": list_scenarios()}


async def install_scenario(scenario_name: str, *, run: bool):
    require_demo_routes()
    # Préparation AVANT toute interruption/reset de l'état existant.
    try:
        scenario = load_scenario(scenario_name)
        if run and scenario.goal is None and scenario.seed_negotiation is None:
            raise HTTPException(400, "Scenario has no goal or seeded negotiation. Load it, then use Start agent.")
        prepared = prepare_scenario(scenario, privacy_guard)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Scenario not found.") from exc
    except (ValidationError, ValueError) as exc:
        logger.warning("Invalid scenario: %s", exc)
        raise HTTPException(400, "Invalid scenario. Existing world was not changed; see server logs.") from exc

    async with maintenance_lock:
        orchestrator.maintenance = True
        try:
            await orchestrator.stop_all()
            async with world_lock:
                apply_prepared_scenario(
                    prepared, world=world, reputation=reputation, personal_agents=personal_agents,
                )
                await websocket_hub.emit(event_type="market_updated", payload={
                    "message": "Scenario loaded. Reload local UI selections if necessary.",
                    "scenario": scenario.name, "reset": True,
                })
                await websocket_hub.emit(event_type="simulation_time_updated", payload={
                    "current_time": world.current_time,
                })
        finally:
            orchestrator.maintenance = False
        initial_step = None
        if run:
            if prepared.seeded_negotiation_id is not None:
                initial_step = await orchestrator.resume(prepared.seeded_negotiation_id)
            elif scenario.goal is not None:
                goal = scenario.goal
                initial_step = await orchestrator.pursue(
                    user_id=goal.user_id, request=goal.request,
                    offered_resources=goal.offered_resources, message=goal.message,
                )
        return {
            "scenario": scenario.name, "description": scenario.description,
            "goal": scenario.goal, "seeded_negotiation_id": prepared.seeded_negotiation_id,
            "initial_step": initial_step, "state": simulation_snapshot(),
        }


@app.post("/dev/scenarios/{scenario_name}/load")
@app.post("/dev/load-scenario/{scenario_name}", include_in_schema=False)
async def load_demo_scenario(scenario_name: str):
    return await install_scenario(scenario_name, run=False)


@app.post("/dev/scenarios/{scenario_name}/run")
async def run_demo_scenario(scenario_name: str):
    return await install_scenario(scenario_name, run=True)


@app.delete("/dev/reset")
async def reset_state():
    require_demo_routes()
    async with maintenance_lock:
        orchestrator.maintenance = True
        try:
            await orchestrator.stop_all()
            async with world_lock:
                world.users.clear()
                world.active_negotiations.clear()
                world.completed_negotiations.clear()
                world.registry = MarketRegistry()
                world._event_queue.clear()
                world._event_counter = count()
                world.event_history.clear()
                world.current_time = datetime.now(timezone.utc)
                personal_agents.clear()
                reputation.reset()
                await websocket_hub.emit(event_type="market_updated", payload={
                    "message": "Local simulation reset.", "reset": True,
                })
                return {"message": "Application state reset.", "current_time": world.current_time}
        finally:
            orchestrator.maintenance = False
