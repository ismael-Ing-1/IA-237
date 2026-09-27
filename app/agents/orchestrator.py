"""Orchestration générique des agents existants, sans noms d'utilisateurs codés en dur.

Périmètre : échanges bilatéraux, médiation, découverte/validation de coalitions,
approbations humaines multi-parties et exécution atomique des coalitions.
"""
from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from collections import defaultdict
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any

from app.agents.coalition_agent import CoalitionAgent, RankedCoalition
from app.agents.mediator_agent import (
    MediationAction,
    MediationResult,
    MediationTrigger,
    MediatorAgent,
)
from app.agents.personal_agent import (
    AgentAction,
    AgentDecision,
    AgentStepResult,
    CandidatePartner,
    InitialOfferOption,
    NegotiationChoiceAction,
    NegotiationResponseOption,
    PersonalAgent,
)
from app.models.negotiation import Negotiation, NegotiationStatus
from app.models.offer import Offer, OfferStatus
from app.models.resource import Resource, ResourceRequest
from app.llm import LLMMode, LLMPolicy, SafeChoice
from app.llm.context import (
    public_candidate_context,
    public_coalition_context,
    public_mediation_context,
    public_negotiation_context,
)
from app.llm.schemas import LLMMediationDecision
from app.privacy import PrivacyAction, PrivacyGuard
from app.reputation import ReputationManager
from app.reputation.reputation import ReputationEventType
from app.simulation import SimulationWorld
from app.tools.coalition_execution import execute_coalition_atomically
from app.tools.need_tools import sync_user_need
from app.tools.coalition_tools import (
    CoalitionDeal,
    CoalitionStatus,
    coalition_signature,
    evaluate_coalition_feasibility,
)
from app.tools.negotiation_tools import (
    accept_offer,
    cancel_negotiation,
    counter_offer,
    reject_negotiation,
)

logger = logging.getLogger(__name__)
EventEmitter = Callable[..., Awaitable[None]]
RUNNABLE = {NegotiationStatus.OPEN, NegotiationStatus.NEGOTIATING}
OPEN_DEAL = RUNNABLE | {
    NegotiationStatus.AGREEMENT_FOUND, NegotiationStatus.WAITING_HUMAN,
    NegotiationStatus.APPROVED,
}


class AgentConflict(ValueError):
    """Commande en conflit avec une négociation déjà prise en charge."""


@dataclass
class ObjectiveContext:
    """Mandat privé en mémoire, jamais inclus dans les snapshots publics."""
    user_id: str
    request: ResourceRequest
    offered_resources: list[Resource]
    message: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    attempted: set[str] = field(default_factory=set)
    attempted_coalitions: set[str] = field(default_factory=set)
    negotiation_ids: set[str] = field(default_factory=set)
    coalition_ids: set[str] = field(default_factory=set)
    state: str = "searching"
    cancelled: bool = False


class AgentOrchestrator:
    def __init__(
        self, *, world: SimulationWorld, reputation: ReputationManager,
        privacy_guard: PrivacyGuard, personal_agents: dict[str, PersonalAgent],
        emit_event: EventEmitter,
        llm_policy: LLMPolicy | None = None,
        lock: asyncio.Lock | None = None,
        step_delay: float = 0.25,
    ) -> None:
        if not math.isfinite(step_delay) or not 0 <= step_delay <= 5:
            raise ValueError("step_delay must be between 0 and 5 seconds.")
        self.world = world
        self.reputation = reputation
        self.privacy_guard = privacy_guard
        self.personal_agents = personal_agents
        self.emit_event = emit_event
        self.llm_policy = llm_policy
        self.lock = lock if lock is not None else asyncio.Lock()
        self.step_delay = step_delay
        self.coalition_agent = CoalitionAgent(world=world, reputation=reputation)
        self.mediator_agent = MediatorAgent()
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._owners: dict[str, str] = {}
        self._goals: dict[str, ResourceRequest] = {}
        self._coalitions: dict[str, list[RankedCoalition]] = {}
        self._coalition_deals: dict[str, CoalitionDeal] = {}
        self._coalition_context: dict[str, str] = {}
        self._coalition_owner: dict[str, str] = {}
        self.maintenance = False
        self._objectives: dict[str, ObjectiveContext] = {}
        self._objective_by_negotiation: dict[str, str] = {}
        self._runtime: dict[str, dict[str, Any]] = {}
        self.max_partner_attempts = 8
        self._mediation_attempted: set[str] = set()


    @property
    def running_count(self) -> int:
        return sum(not task.done() for task in self._tasks.values())

    def is_running(self, negotiation_id: str) -> bool:
        task = self._tasks.get(negotiation_id)
        return task is not None and not task.done()

    def get_personal_agent(self, user_id: str) -> PersonalAgent:
        if self.world.get_user(user_id) is None:
            raise ValueError("Unknown user.")
        if user_id not in self.personal_agents:
            self.personal_agents[user_id] = PersonalAgent(
                user_id=user_id, world=self.world, reputation=self.reputation,
                privacy_guard=self.privacy_guard,
            )
        return self.personal_agents[user_id]

    def _ensure_available(self) -> None:
        if self.maintenance:
            raise AgentConflict("The simulator is resetting. Try again shortly.")

    async def _llm_choose(
        self,
        *,
        task: str,
        user_id: str | None,
        entity_id: str | None,
        context: dict,
        options: list[SafeChoice],
        fallback_choice_id: str,
    ):
        if self.llm_policy is None:
            return None

        if self.llm_policy.should_call:
            await self._emit(
                "llm_thinking",
                user_id,
                entity_id,
                {
                    "task": task,
                    "model": (
                        self.llm_policy
                        .config.model
                    ),
                    "mode": (
                        self.llm_policy
                        .mode.value
                    ),
                    "message": (
                        "LLM is evaluating locally "
                        "pre-validated choices."
                    ),
                },
            )

        outcome = await self.llm_policy.choose(
            task=task,
            context=context,
            options=options,
            fallback_choice_id=(
                fallback_choice_id
            ),
        )

        if outcome.fallback_reason and (
            outcome.mode == LLMMode.ACTIVE
            or outcome.model_choice_id is None
        ):
            await self._emit(
                "llm_fallback",
                user_id,
                entity_id,
                {
                    "task": task,
                    "model": outcome.model,
                    "mode": outcome.mode.value,
                    "message": (
                        "Deterministic policy used: "
                        f"{outcome.fallback_reason}."
                    ),
                },
            )
        elif outcome.mode == LLMMode.SHADOW:
            await self._emit(
                "llm_shadow_decision",
                user_id,
                entity_id,
                {
                    "task": task,
                    "model": outcome.model,
                    "model_choice_id": (
                        outcome.model_choice_id
                    ),
                    "effective_choice_id": (
                        outcome.effective_choice_id
                    ),
                    "confidence": (
                        outcome.confidence
                    ),
                    "message": (
                        "Shadow LLM decision observed; "
                        "deterministic policy remains "
                        "authoritative."
                    ),
                },
            )
        elif outcome.mode == LLMMode.ACTIVE:
            await self._emit(
                "llm_decision",
                user_id,
                entity_id,
                {
                    "task": task,
                    "model": outcome.model,
                    "choice_id": (
                        outcome.effective_choice_id
                    ),
                    "confidence": (
                        outcome.confidence
                    ),
                    "message": outcome.reason,
                },
            )

        return outcome

    async def _choose_partner_with_llm(
        self,
        *,
        agent: PersonalAgent,
        resource_type: str,
        candidates: list[CandidatePartner],
        entity_id: str | None = None,
    ) -> CandidatePartner:
        if not candidates:
            raise ValueError(
                "No eligible candidates."
            )

        limited = candidates[
            : (
                self.llm_policy
                .config.max_candidates
                if self.llm_policy
                is not None
                else len(candidates)
            )
        ]

        if self.llm_policy is None:
            return limited[0]

        options = [
            SafeChoice(
                choice_id=item.user_id,
                label=(
                    f"Provider {item.display_name}"
                ),
                description=(
                    "Eligible public provider with "
                    f"reputation {item.reputation:.3f}. "
                    "Offers: "
                    + ", ".join(item.offered_resource_types)
                    + ". Publicly requests: "
                    + (
                        ", ".join(item.requested_resource_types)
                        if item.requested_resource_types
                        else "none advertised"
                    )
                    + "."
                ),
                public_terms={
                    "provider_id": item.user_id,
                    "reputation": item.reputation,
                    "offered_resource_types": (
                        item.offered_resource_types
                    ),
                    "requested_resource_types": (
                        item.requested_resource_types
                    ),
                },
            )
            for item in limited
        ]

        outcome = await self._llm_choose(
            task="select_provider",
            user_id=agent.user_id,
            entity_id=entity_id,
            context=public_candidate_context(
                strategy=agent.user.strategy.value,
                requested_resource_type=(
                    resource_type
                ),
                candidates=limited,
            ),
            options=options,
            fallback_choice_id=(
                limited[0].user_id
            ),
        )

        if outcome is None:
            return limited[0]

        return next(
            item
            for item in limited
            if item.user_id
            == outcome.effective_choice_id
        )


    @staticmethod
    def _public_terms(
        *,
        offered_resources,
        requested_resources,
    ) -> dict:
        return {
            "offered_resources": [
                {
                    "resource_type": item.resource_type,
                    "quantity": item.quantity,
                    "unit": item.unit,
                }
                for item in offered_resources
            ],
            "requested_resources": [
                {
                    "resource_type": item.resource_type,
                    "quantity": item.quantity,
                    "unit": item.unit,
                }
                for item in requested_resources
            ],
        }

    async def _choose_initial_offer_with_llm(
        self,
        *,
        agent: PersonalAgent,
        partner: CandidatePartner,
        authorized_offered_resources: list[Resource],
        request: ResourceRequest,
        entity_id: str | None,
    ) -> InitialOfferOption:
        options = agent.build_initial_offer_options(
            partner_id=partner.user_id,
            authorized_offered_resources=[
                item.model_copy(deep=True)
                for item
                in authorized_offered_resources
            ],
            requested_resources=[
                request.model_copy(deep=True)
            ],
        )

        if not options:
            raise ValueError(
                "No safe initial offer can be generated."
            )

        fallback = next(
            (
                item
                for item in options
                if item.choice_id
                == "initial_direct"
            ),
            options[0],
        )

        safe_options = [
            SafeChoice(
                choice_id=item.choice_id,
                label=item.label,
                description=(
                    item.reason
                    + " "
                    + agent._terms_text(
                        item.offered_resources,
                        item.requested_resources,
                    )
                ),
                public_terms=self._public_terms(
                    offered_resources=(
                        item.offered_resources
                    ),
                    requested_resources=(
                        item.requested_resources
                    ),
                ),
            )
            for item in options
        ]

        outcome = await self._llm_choose(
            task="compose_initial_offer",
            user_id=agent.user_id,
            entity_id=entity_id,
            context={
                "strategy": (
                    agent.user.strategy.value
                ),
                "provider": {
                    "user_id": partner.user_id,
                    "display_name": (
                        partner.display_name
                    ),
                    "reputation": (
                        partner.reputation
                    ),
                    "public_requested_resource_types": (
                        partner.requested_resource_types
                    ),
                },
                "note": (
                    "All listed proposals are already "
                    "locally safe. Choose the opening "
                    "that best fits the strategy and "
                    "public compatibility."
                ),
            },
            options=safe_options,
            fallback_choice_id=(
                fallback.choice_id
            ),
        )

        chosen_id = (
            outcome.effective_choice_id
            if outcome is not None
            else fallback.choice_id
        )

        chosen = next(
            item
            for item in options
            if item.choice_id == chosen_id
        )

        await self._emit(
            "llm_policy_validated",
            agent.user_id,
            entity_id,
            {
                "task": "compose_initial_offer",
                "choice_id": chosen.choice_id,
                "terms": self._public_terms(
                    offered_resources=(
                        chosen.offered_resources
                    ),
                    requested_resources=(
                        chosen.requested_resources
                    ),
                ),
                "message": (
                    "Selected initial offer passed "
                    "the local policy boundary."
                ),
            },
        )

        return chosen

    async def _choose_coalition_with_llm(
        self,
        *,
        user_id: str,
        candidates: list[RankedCoalition],
        entity_id: str | None,
    ) -> list[RankedCoalition]:
        if (
            not candidates
            or self.llm_policy is None
        ):
            return candidates

        limited = candidates[
            : self.llm_policy.config.max_candidates
        ]

        options = [
            SafeChoice(
                choice_id=item.proposal.id,
                label=(
                    "Coalition "
                    + " → ".join(
                        item.proposal
                        .participant_ids
                    )
                ),
                description=(
                    "Already-feasible coalition; "
                    f"public score {item.score:.3f}, "
                    "average reputation "
                    f"{item.average_reputation:.3f}."
                ),
            )
            for item in limited
        ]

        outcome = await self._llm_choose(
            task="rank_safe_coalitions",
            user_id=user_id,
            entity_id=entity_id,
            context=public_coalition_context(
                limited
            ),
            options=options,
            fallback_choice_id=(
                limited[0].proposal.id
            ),
        )

        if outcome is None:
            return candidates

        chosen_id = (
            outcome.effective_choice_id
        )
        chosen = next(
            item
            for item in limited
            if item.proposal.id
            == chosen_id
        )

        return [
            chosen,
            *[
                item
                for item in candidates
                if item.proposal.id
                != chosen_id
            ],
        ]

    def _llm_mediation_proposal(
        self,
        negotiation: Negotiation,
        decision: LLMMediationDecision,
    ):
        """
        Convert an LLM mediation suggestion into a domain proposal only if
        every resource/quantity remains inside the latest PUBLIC bargaining
        interval. Private constraints are checked later by PersonalAgents.
        """
        from app.agents.mediator_agent import (
            MediationProposal,
        )

        if decision.action != "suggest_counter":
            return None

        if len(negotiation.offers) < 2:
            return None

        previous = negotiation.offers[-2]
        latest = negotiation.offers[-1]

        expected_sender = latest.receiver_id
        expected_receiver = latest.sender_id

        if (
            decision.sender_id
            != expected_sender
            or decision.receiver_id
            != expected_receiver
        ):
            return None

        offered: list[Resource] = []
        for line in decision.offered_resources:
            left = next(
                (
                    item
                    for item
                    in previous.offered_resources
                    if (
                        item.resource_type
                        == line.resource_type
                        and item.unit
                        == line.unit
                    )
                ),
                None,
            )
            right = next(
                (
                    item
                    for item
                    in latest.requested_resources
                    if (
                        item.resource_type
                        == line.resource_type
                        and item.unit
                        == line.unit
                    )
                ),
                None,
            )

            if left is None or right is None:
                return None

            low = min(
                left.quantity,
                right.quantity,
            )
            high = max(
                left.quantity,
                right.quantity,
            )

            if not low <= line.quantity <= high:
                return None

            offered.append(
                Resource(
                    resource_type=line.resource_type,
                    quantity=line.quantity,
                    unit=line.unit,
                    attributes=dict(
                        left.attributes
                    ),
                )
            )

        requested: list[ResourceRequest] = []
        for line in decision.requested_resources:
            left = next(
                (
                    item
                    for item
                    in previous.requested_resources
                    if (
                        item.resource_type
                        == line.resource_type
                        and item.unit
                        == line.unit
                    )
                ),
                None,
            )
            right = next(
                (
                    item
                    for item
                    in latest.offered_resources
                    if (
                        item.resource_type
                        == line.resource_type
                        and item.unit
                        == line.unit
                    )
                ),
                None,
            )

            if left is None or right is None:
                return None

            low = min(
                left.quantity,
                right.quantity,
            )
            high = max(
                left.quantity,
                right.quantity,
            )

            if not low <= line.quantity <= high:
                return None

            requested.append(
                ResourceRequest(
                    resource_type=line.resource_type,
                    quantity=line.quantity,
                    unit=line.unit,
                    deadline=left.deadline,
                    attributes=dict(
                        left.attributes
                    ),
                )
            )

        if not offered or not requested:
            return None

        return MediationProposal(
            sender_id=expected_sender,
            receiver_id=expected_receiver,
            offered_resources=offered,
            requested_resources=requested,
        )

    def _ensure_no_objective(self, user_id: str) -> None:
        if any(ctx.user_id == user_id and not ctx.cancelled and ctx.state in {
            "searching", "negotiating", "waiting_human", "approved", "searching_coalition",
            "coalition_validating", "coalition_waiting_humans", "coalition_approved",
        } for ctx in self._objectives.values()):
            raise AgentConflict("An objective is already active for this user.")
        for negotiation_id, owner in self._owners.items():
            negotiation = self.world.active_negotiations.get(negotiation_id)
            if owner == user_id and negotiation is not None and negotiation.status in OPEN_DEAL:
                raise AgentConflict("An objective is already active for this user.")

    def _validate_amounts(self, resources: list[Resource] | list[ResourceRequest]) -> None:
        if not resources:
            raise ValueError("At least one resource is required.")
        for resource in resources:
            if not math.isfinite(resource.quantity) or resource.quantity <= 0:
                raise ValueError("Resource quantities must be finite and positive.")
            if not resource.resource_type.strip() or not resource.unit.strip():
                raise ValueError("Resource type and unit are required.")

    def validate_outgoing(
        self, user_id: str, resources: list[Resource] | list[ResourceRequest],
    ) -> None:
        """Agrège les lignes pour ne pas contourner une limite avec des doublons."""
        self._validate_amounts(resources)
        user = self.world.get_user(user_id)
        if user is None or not user.online:
            raise ValueError("User is unknown or offline.")
        totals: dict[tuple[str, str], float] = defaultdict(float)
        units: dict[str, set[str]] = defaultdict(set)
        for resource in resources:
            totals[(resource.resource_type, resource.unit)] += resource.quantity
            units[resource.resource_type].add(resource.unit)
        for (resource_type, unit), quantity in totals.items():
            available = sum(r.quantity for r in user.resources
                            if r.resource_type == resource_type and r.unit == unit)
            if not math.isfinite(available) or quantity > available:
                raise ValueError("Outgoing offer is not feasible for its owner.")
            limit = user.constraints.max_quantity_to_give.get(resource_type)
            if limit is not None:
                # Le modèle de limite est par type, pas par unité : aucune conversion inventée.
                if len(units[resource_type]) > 1:
                    raise ValueError("Mixed units for a privately limited resource are ambiguous.")
                if not math.isfinite(limit) or quantity > limit:
                    raise ValueError("Outgoing offer violates the owner's private policy.")

    def validate_settlement(self, negotiation: Negotiation) -> None:
        """Vérification avant validation/exécution ; ne réalise aucun transfert."""
        if len(set(negotiation.participant_ids)) != 2:
            raise ValueError("This settlement path supports bilateral deals only.")
        offer = negotiation.get_offer(negotiation.accepted_offer_id or "")
        if offer is None or offer.status != OfferStatus.ACCEPTED:
            raise ValueError("No accepted offer.")
        if offer.is_expired():
            raise ValueError("Accepted offer has expired.")
        if {offer.sender_id, offer.receiver_id} != set(negotiation.participant_ids):
            raise ValueError("Offer participants do not match the negotiation.")
        for owner, partner, outgoing in (
            (offer.sender_id, offer.receiver_id, offer.offered_resources),
            (offer.receiver_id, offer.sender_id, offer.requested_resources),
        ):
            self.validate_outgoing(owner, outgoing)
            user = self.world.get_user(owner)
            decision = self.privacy_guard.check_offer(
                user, offer, partner_reputation=self.reputation.get_score(partner),
            )
            if decision.action == PrivacyAction.BLOCK:
                raise ValueError("The accepted terms are no longer allowed.")
        goal = self._goals.get(negotiation.id)
        owner = self._owners.get(negotiation.id)
        if goal is not None and owner is not None:
            incoming = offer.requested_resources if owner == offer.sender_id else offer.offered_resources
            if not self._satisfies(goal, incoming):
                raise ValueError("The agreement does not satisfy the original objective.")

    @staticmethod
    def _satisfies(goal: ResourceRequest, incoming: Any) -> bool:
        return sum(r.quantity for r in incoming
                   if r.resource_type == goal.resource_type and r.unit == goal.unit) >= goal.quantity

    async def pursue(
        self, *, user_id: str, request: ResourceRequest,
        offered_resources: list[Resource], message: str | None = None,
    ) -> AgentStepResult:
        async with self.lock:
            self._ensure_available()
            self._ensure_no_objective(user_id)
            agent = self.get_personal_agent(user_id)
            self._validate_amounts([request])
            self.validate_outgoing(user_id, offered_resources)
            if request.deadline is not None:
                if request.deadline.tzinfo is None or request.deadline.utcoffset() is None:
                    raise ValueError("The deadline must include a timezone.")
                if request.deadline <= self.world.current_time:
                    raise ValueError("The objective deadline has passed in simulation time.")

            # The objective form edits the owner's remaining demand.
            # Keep a snapshot so a failed Start Agent does not corrupt needs.
            user = self.world.get_user(user_id)
            if user is None:
                raise ValueError("Objective owner disappeared.")

            previous_needs = [
                need.model_copy(deep=True)
                for need in user.needs
            ]

            synced_request = sync_user_need(
                user,
                request,
            )
            request = synced_request.model_copy(deep=True)

            await self._emit("agent_started", user_id, message="Agent objective started.")
            await self._decision(user_id, AgentDecision(
                action=AgentAction.SEARCH_MARKET, reason="Searching the available market.",
            ))
            context = ObjectiveContext(
                user_id=user_id, request=request.model_copy(deep=True),
                offered_resources=[r.model_copy(deep=True) for r in offered_resources],
                message=message,
            )
            self._objectives[context.id] = context
            try:
                candidates = agent.discover_candidates(
                    request.resource_type
                )

                if candidates:
                    candidate = (
                        await self
                        ._choose_partner_with_llm(
                            agent=agent,
                            resource_type=(
                                request.resource_type
                            ),
                            candidates=candidates,
                            entity_id=context.id,
                        )
                    )

                    opening = (
                        await self
                        ._choose_initial_offer_with_llm(
                            agent=agent,
                            partner=candidate,
                            authorized_offered_resources=(
                                offered_resources
                            ),
                            request=request,
                            entity_id=context.id,
                        )
                    )

                    result = agent.start_negotiation(
                        partner_id=candidate.user_id,
                        offered_resources=[
                            item.model_copy(deep=True)
                            for item
                            in opening.offered_resources
                        ],
                        requested_resources=[
                            item.model_copy(deep=True)
                            for item
                            in opening.requested_resources
                        ],
                        message=message,
                    )
                else:
                    result = AgentStepResult(
                        decision=AgentDecision(
                            action=(
                                AgentAction
                                .SEARCH_COALITION
                            ),
                            reason=(
                                "No acceptable direct "
                                "provider was found."
                            ),
                        )
                    )
            except Exception:
                user.needs = [
                    need.model_copy(deep=True)
                    for need in previous_needs
                ]
                context.state = "failed"
                self._set_runtime(user_id, "failed", "Objective could not be started.", objective=context)
                await self._changed()
                raise
            # Une copie conserve la réponse initiale même si le worker continue ensuite.
            response = result.model_copy(deep=True)
            if result.negotiation is not None and result.offer is not None:
                negotiation = result.negotiation
                self._attach_attempt(context, result)
                self._owners[negotiation.id] = user_id
                self._goals[negotiation.id] = request.model_copy(deep=True)
                # Les noms d'utilisateurs ne sont jamais utilisés pour router les actions.
                partner_id = result.offer.receiver_id
                await self._emit("provider_found", user_id, negotiation.id, {
                    "provider_id": partner_id,
                    "reputation": self.reputation.get_score(partner_id),
                    "message": "Provider selected by the personal agent.",
                })
                await self._decision(user_id, result.decision)
                await self._emit("negotiation_started", user_id, negotiation.id, {
                    "negotiation": negotiation, "message": "Negotiation created.",
                })
                await self._emit("offer_sent", user_id, negotiation.id, {
                    "negotiation_id": negotiation.id, "offer": result.offer,
                    "message": "Initial offer sent.",
                })
                self._start_worker(negotiation.id, self._run(negotiation.id, user_id))
            else:
                await self._decision(user_id, result.decision)
                # Cette branche ne crée pas de faux objet Negotiation pour une coalition.
                key = f"search:{user_id}"
                if self.is_running(key):
                    raise AgentConflict("A coalition search is already running.")
                self._start_worker(key, self._search_job(user_id, request, context.id))
            await self._changed()
            return response

    async def resume(self, negotiation_id: str) -> AgentStepResult:
        async with self.lock:
            self._ensure_available()
            if self.is_running(negotiation_id):
                raise AgentConflict("Negotiation is already running.")
            negotiation, offer = self._pending(negotiation_id)
            owner = self._owners.setdefault(negotiation_id, negotiation.offers[0].sender_id)
            # Un scénario préchargé peut être repris avec son mandat initial unique.
            if negotiation_id not in self._objective_by_negotiation:
                first = negotiation.offers[0]
                if len(first.requested_resources) == 1:
                    context = ObjectiveContext(
                        user_id=owner, request=first.requested_resources[0].model_copy(deep=True),
                        offered_resources=[r.model_copy(deep=True) for r in first.offered_resources],
                        message=first.message,
                    )
                    context.negotiation_ids.add(negotiation_id)
                    context.attempted.add(first.receiver_id)
                    context.state = "negotiating"
                    self._objectives[context.id] = context
                    self._objective_by_negotiation[negotiation_id] = context.id
                    self._goals[negotiation_id] = context.request
            self._set_runtime(owner, "negotiating", "Resuming the negotiation.", negotiation_id)
            result = AgentStepResult(
                decision=AgentDecision(
                    action=AgentAction.START_NEGOTIATION,
                    reason="Resuming the existing negotiation from its latest offer.",
                    partner_id=offer.receiver_id, negotiation_id=negotiation_id, offer_id=offer.id,
                ), negotiation=negotiation, offer=offer,
            ).model_copy(deep=True)
            self._start_worker(negotiation_id, self._run(negotiation_id, owner))
            return result

    def _pending(self, negotiation_id: str) -> tuple[Negotiation, Offer]:
        negotiation = self.world.active_negotiations.get(negotiation_id)
        if negotiation is None or negotiation.status not in RUNNABLE:
            raise AgentConflict("Negotiation is not open for agent processing.")
        if len(negotiation.participant_ids) != 2 or len(set(negotiation.participant_ids)) != 2:
            raise ValueError("Bilateral orchestration needs two distinct participants.")
        offer = negotiation.get_last_offer()
        if offer is None or offer.status != OfferStatus.PENDING:
            raise AgentConflict("No pending offer to process.")
        if {offer.sender_id, offer.receiver_id} != set(negotiation.participant_ids):
            raise ValueError("Invalid offer participants.")
        if offer.is_expired():
            offer.status = OfferStatus.EXPIRED
            raise ValueError("Offer expired.")
        return negotiation, offer

    async def handle_offer_once(
        self, *, user_id: str, negotiation_id: str, offer_id: str,
    ) -> AgentStepResult:
        async with self.lock:
            self._ensure_available()
            if self.is_running(negotiation_id):
                raise AgentConflict("Automatic worker owns this negotiation.")
            negotiation, offer = self._pending(negotiation_id)
            if offer.id != offer_id or offer.receiver_id != user_id:
                raise AgentConflict("Only the receiver may process the latest pending offer.")
            owner = self._owners.setdefault(negotiation_id, negotiation.offers[0].sender_id)
            return (await self._step(negotiation, offer, owner)).model_copy(deep=True)


    async def _step(
        self,
        negotiation: Negotiation,
        offer: Offer,
        owner: str,
    ) -> AgentStepResult:
        receiver = self.get_personal_agent(
            offer.receiver_id
        )

        if not receiver.user.online:
            raise ValueError(
                "Receiver is offline."
            )

        self.validate_outgoing(
            offer.sender_id,
            offer.offered_resources,
        )

        goal = self._goals.get(
            negotiation.id
        )
        if (
            goal is not None
            and goal.deadline is not None
            and goal.deadline
            <= self.world.current_time
        ):
            raise ValueError(
                "Objective deadline has passed."
            )

        await self._emit(
            "agent_started",
            receiver.user_id,
            negotiation.id,
            message=(
                "Evaluating the latest incoming offer."
            ),
        )

        response_set = (
            receiver.build_response_options(
                negotiation,
                offer,
            )
        )

        options = list(
            response_set.options
        )

        # Once mediation has already been attempted for this negotiation,
        # do not allow the model to repeatedly request it.
        if (
            negotiation.id
            in self._mediation_attempted
        ):
            options = [
                item
                for item in options
                if (
                    item.action
                    != NegotiationChoiceAction
                    .ASK_MEDIATOR
                )
            ]

        if not options:
            raise ValueError(
                "No locally safe negotiation action is available."
            )

        fallback_choice_id = (
            response_set.fallback_choice_id
        )

        if not any(
            item.choice_id
            == fallback_choice_id
            for item in options
        ):
            fallback_choice_id = (
                options[0].choice_id
            )

        safe_options = [
            SafeChoice(
                choice_id=item.choice_id,
                label=item.label,
                description=(
                    item.reason
                    + (
                        " "
                        + receiver._terms_text(
                            item.offered_resources,
                            item.requested_resources,
                        )
                        if (
                            item.action
                            == NegotiationChoiceAction
                            .COUNTER
                        )
                        else ""
                    )
                ),
                public_terms=(
                    self._public_terms(
                        offered_resources=(
                            item.offered_resources
                        ),
                        requested_resources=(
                            item.requested_resources
                        ),
                    )
                    if (
                        item.action
                        == NegotiationChoiceAction
                        .COUNTER
                    )
                    else {
                        "action": (
                            item.action.value
                        )
                    }
                ),
            )
            for item in options
        ]

        outcome = None
        if self.llm_policy is not None:
            outcome = await self._llm_choose(
                task="choose_full_negotiation_turn",
                user_id=receiver.user_id,
                entity_id=negotiation.id,
                context=public_negotiation_context(
                    negotiation=negotiation,
                    receiver_strategy=(
                        receiver.user.strategy.value
                    ),
                ),
                options=safe_options,
                fallback_choice_id=(
                    fallback_choice_id
                ),
            )

        selected_id = (
            outcome.effective_choice_id
            if outcome is not None
            else fallback_choice_id
        )

        selected = next(
            item
            for item in options
            if item.choice_id == selected_id
        )

        await self._emit(
            "llm_policy_validated",
            receiver.user_id,
            negotiation.id,
            {
                "task": (
                    "choose_full_negotiation_turn"
                ),
                "choice_id": (
                    selected.choice_id
                ),
                "action": (
                    selected.action.value
                ),
                "terms": (
                    self._public_terms(
                        offered_resources=(
                            selected
                            .offered_resources
                        ),
                        requested_resources=(
                            selected
                            .requested_resources
                        ),
                    )
                    if (
                        selected.action
                        == NegotiationChoiceAction
                        .COUNTER
                    )
                    else None
                ),
                "message": (
                    "LLM-selected action is one of "
                    "the locally validated options."
                ),
            },
        )

        result = (
            receiver.apply_response_option(
                negotiation,
                offer,
                selected,
            )
        )

        await self._decision(
            receiver.user_id,
            result.decision,
            update_runtime=(
                receiver.user_id == owner
            ),
        )

        # Mediator is an explicit model decision and does NOT reject/mutate
        # the latest pending offer before mediation begins.
        if (
            result.decision.action
            == AgentAction.ASK_MEDIATOR
        ):
            await self._emit(
                "negotiation_updated",
                receiver.user_id,
                negotiation.id,
                {
                    "negotiation": negotiation,
                    "message": (
                        "PersonalAgent requested "
                        "public-only mediation."
                    ),
                },
            )

            handled = (
                await self
                ._attempt_automatic_mediation(
                    negotiation,
                    owner,
                    force=True,
                )
            )

            if not handled:
                await self._changed()

            return result

        event_type = {
            AgentAction.ACCEPT: (
                "offer_accepted"
            ),
            AgentAction.REJECT: (
                "offer_rejected"
            ),
            AgentAction.COUNTER: (
                "counter_offer_sent"
            ),
        }.get(result.decision.action)

        if event_type:
            await self._emit(
                event_type,
                receiver.user_id,
                negotiation.id,
                {
                    "negotiation_id": (
                        negotiation.id
                    ),
                    "offer": result.offer,
                    "message": (
                        "Agent processed the offer "
                        "using the selected safe policy."
                    ),
                },
            )

        if (
            result.decision.action
            == AgentAction.ACCEPT
        ):
            self.validate_settlement(
                negotiation
            )

            decision = (
                self.get_personal_agent(
                    owner
                )
                .request_human_validation(
                    negotiation
                )
            )

            await self._decision(
                owner,
                decision,
            )

            await self._emit(
                "human_approval_required",
                owner,
                negotiation.id,
                {
                    "negotiation": negotiation,
                    "message": (
                        "Review the agreed terms "
                        "before approving."
                    ),
                },
            )

        await self._emit(
            "negotiation_updated",
            receiver.user_id,
            negotiation.id,
            {
                "negotiation": negotiation
            },
        )

        await self._changed()
        return result

    async def _run(self, negotiation_id: str, owner: str) -> None:
        # Un tour = une réponse du destinataire, non un couple de noms prédéfini.
        try:
            budget = 100  # Plafond supplémentaire, sans relever les limites du modèle.
            for _ in range(budget):
                # Cadence de démonstration seulement ; le temps virtuel ne change pas.
                await asyncio.sleep(self.step_delay)
                async with self.lock:
                    negotiation = self.world.active_negotiations.get(negotiation_id)
                    if negotiation is None or negotiation.status not in RUNNABLE:
                        return
                    negotiation, offer = self._pending(negotiation_id)

                    if (
                        negotiation.id not in self._mediation_attempted
                        and self.mediator_agent.should_intervene(negotiation)
                    ):
                        handled = await self._attempt_automatic_mediation(
                            negotiation,
                            owner,
                        )
                        if handled:
                            return
                        negotiation, offer = self._pending(negotiation_id)

                    result = await self._step(negotiation, offer, owner)
                    if result.decision.action == AgentAction.ACCEPT:
                        return
                    if result.decision.action == AgentAction.COUNTER:
                        if result.offer is None or result.offer.receiver_id != offer.sender_id:
                            raise ValueError("Invalid counter-offer direction.")
                        continue
                    if result.decision.action == AgentAction.REJECT:
                        await self._fallback(negotiation, owner)
                        return
                    if result.decision.action == AgentAction.ASK_MEDIATOR:
                        if negotiation.status in RUNNABLE:
                            continue
                        return
                    return
            raise ValueError("Orchestration safety limit reached.")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Agent run failed for negotiation %s", negotiation_id)
            async with self.lock:
                negotiation = self.world.active_negotiations.get(negotiation_id)
                if negotiation is not None and negotiation.status in RUNNABLE:
                    negotiation.fail()
                self._set_runtime(owner, "failed", "Agent processing failed; inspect backend logs.", negotiation_id)
                # Ne pas diffuser str(exc) : des erreurs métier peuvent contenir des secrets.
                await self._emit("error", owner, negotiation_id, {
                    "message": "Agent processing stopped safely. Check the backend logs.",
                    "code": "agent_run_failed",
                })
                await self._changed()
        finally:
            # Le worker s'arrête naturellement à un checkpoint (par exemple
            # WAITING_HUMAN). Cela ne signifie pas que l'objectif de l'agent
            # est annulé, donc on publie une notification et non AGENT_STOPPED.
            await self._emit(
                "agent_notified",
                owner,
                negotiation_id,
                message="Automatic negotiation loop paused at the current checkpoint.",
            )

    async def _fallback(
        self,
        negotiation: Negotiation,
        owner: str,
    ) -> None:
        """
        Give the mediator one final chance before moving
        to a different provider / coalition fallback.
        """

        if (
            len(negotiation.offers) >= 2
            and negotiation.id not in self._mediation_attempted
        ):
            handled = await self._attempt_automatic_mediation(
                negotiation,
                owner,
                force=True,
            )
            if handled:
                return

        await self._close_bilateral_and_continue(
            negotiation,
            owner,
            reason=(
                "Direct negotiation ended without "
                "a mutually acceptable agreement."
            ),
        )

    async def _close_bilateral_and_continue(
        self,
        negotiation: Negotiation,
        owner: str,
        *,
        reason: str,
    ) -> None:
        if negotiation.status in RUNNABLE:
            negotiation.fail()

        await self._emit(
            "negotiation_updated",
            owner,
            negotiation.id,
            {
                "negotiation": negotiation,
                "message": reason,
            },
        )

        context = self._context(negotiation.id)

        if context is not None and not context.cancelled:
            await self._schedule_alternative(
                context,
                negotiation.id,
            )
        else:
            await self._search_coalition(
                owner,
                self._goals.get(negotiation.id),
                negotiation.id,
            )

        await self._changed()

    async def _attempt_automatic_mediation(
        self,
        negotiation: Negotiation,
        owner: str,
        *,
        force: bool = False,
    ) -> bool:
        """
        Operational mediation.

        The mediator only proposes public terms. Both PersonalAgents
        must privately approve them before they become a real offer.
        """

        if negotiation.id in self._mediation_attempted:
            return False

        trigger = self.mediator_agent.intervention_trigger(
            negotiation
        )

        if trigger is None and not force:
            return False

        if trigger is None:
            trigger = MediationTrigger.ROUND_PRESSURE

        self._mediation_attempted.add(
            negotiation.id
        )

        await self._emit(
            "mediation_started",
            owner,
            negotiation.id,
            {
                "negotiation_id": negotiation.id,
                "trigger": trigger.value,
                "message": (
                    "PersonalAgents have not reached agreement; "
                    "the mediator is inspecting only public offers."
                ),
            },
        )

        result = self.mediator_agent.mediate(
            negotiation,
            trigger=trigger,
        )

        if (
            self.llm_policy is not None
            and result.action
            == MediationAction.SUGGEST_COUNTER
            and result.proposal is not None
        ):
            if self.llm_policy.should_call:
                await self._emit(
                    "llm_thinking",
                    owner,
                    negotiation.id,
                    {
                        "task": "mediate_public_offers",
                        "model": (
                            self.llm_policy
                            .config.model
                        ),
                        "mode": (
                            self.llm_policy
                            .mode.value
                        ),
                        "message": (
                            "LLM mediator is reviewing "
                            "public offers only."
                        ),
                    },
                )

            llm_mediation = (
                await self.llm_policy.mediate(
                    context=(
                        public_mediation_context(
                            negotiation
                        )
                    )
                )
            )

            suggestion = (
                llm_mediation.suggestion
            )
            candidate_proposal = (
                self._llm_mediation_proposal(
                    negotiation,
                    suggestion,
                )
                if suggestion is not None
                else None
            )

            if (
                self.llm_policy.mode
                == LLMMode.ACTIVE
                and suggestion is not None
                and suggestion.action
                == "suggest_coalition"
            ):
                result = MediationResult(
                    action=(
                        MediationAction
                        .SUGGEST_COALITION
                    ),
                    reason=suggestion.reason,
                    trigger=trigger,
                )
                await self._emit(
                    "llm_decision",
                    owner,
                    negotiation.id,
                    {
                        "task": "mediate_public_offers",
                        "model": llm_mediation.model,
                        "choice_id": (
                            "suggest_coalition"
                        ),
                        "message": (
                            suggestion.reason
                        ),
                    },
                )
            elif (
                self.llm_policy.mode
                == LLMMode.ACTIVE
                and candidate_proposal
                is not None
            ):
                result = MediationResult(
                    action=(
                        MediationAction
                        .SUGGEST_COUNTER
                    ),
                    reason=suggestion.reason,
                    proposal=candidate_proposal,
                    trigger=trigger,
                )
                await self._emit(
                    "llm_decision",
                    owner,
                    negotiation.id,
                    {
                        "task": "mediate_public_offers",
                        "model": llm_mediation.model,
                        "choice_id": (
                            "suggest_counter"
                        ),
                        "message": (
                            suggestion.reason
                        ),
                    },
                )
            elif (
                self.llm_policy.mode
                == LLMMode.SHADOW
                and suggestion is not None
            ):
                await self._emit(
                    "llm_shadow_decision",
                    owner,
                    negotiation.id,
                    {
                        "task": "mediate_public_offers",
                        "model": llm_mediation.model,
                        "model_choice_id": (
                            suggestion.action
                        ),
                        "effective_choice_id": (
                            result.action.value
                        ),
                        "message": (
                            "Shadow mediator suggestion "
                            "observed; deterministic "
                            "midpoint remains active."
                        ),
                    },
                )
            elif (
                llm_mediation.error
                is not None
                or (
                    suggestion is not None
                    and suggestion.action
                    == "suggest_counter"
                    and candidate_proposal
                    is None
                )
            ):
                await self._emit(
                    "llm_fallback",
                    owner,
                    negotiation.id,
                    {
                        "task": "mediate_public_offers",
                        "model": llm_mediation.model,
                        "message": (
                            "LLM mediation was unavailable "
                            "or outside the public bargaining "
                            "bounds; deterministic midpoint used."
                        ),
                    },
                )

        await self._emit(
            "mediation_suggestion",
            owner,
            negotiation.id,
            {
                "negotiation_id": negotiation.id,
                "result": result,
                "message": result.reason,
            },
        )

        if result.action == MediationAction.NO_ACTION:
            return False

        if (
            result.action == MediationAction.SUGGEST_COALITION
            or result.proposal is None
        ):
            await self._close_bilateral_and_continue(
                negotiation,
                owner,
                reason=(
                    "Mediator found no useful bilateral compromise."
                ),
            )
            return True

        proposal = result.proposal

        sender_agent = self.get_personal_agent(
            proposal.sender_id
        )
        receiver_agent = self.get_personal_agent(
            proposal.receiver_id
        )

        sender_evaluation = (
            sender_agent.evaluate_mediation_proposal(
                proposal
            )
        )
        receiver_evaluation = (
            receiver_agent.evaluate_mediation_proposal(
                proposal
            )
        )

        for evaluation in (
            sender_evaluation,
            receiver_evaluation,
        ):
            await self._emit(
                "agent_notified",
                evaluation.user_id,
                negotiation.id,
                {
                    "negotiation_id": negotiation.id,
                    "mediation": True,
                    "accepted": evaluation.accepted,
                    "message": evaluation.reason,
                },
            )

        if not (
            sender_evaluation.accepted
            and receiver_evaluation.accepted
        ):
            await self._close_bilateral_and_continue(
                negotiation,
                owner,
                reason=(
                    "At least one PersonalAgent rejected "
                    "the mediator compromise."
                ),
            )
            return True

        latest = negotiation.get_last_offer()

        if (
            latest is None
            or latest.status != OfferStatus.PENDING
        ):
            await self._close_bilateral_and_continue(
                negotiation,
                owner,
                reason=(
                    "Mediator compromise could not be attached "
                    "to the latest pending offer."
                ),
            )
            return True

        if not (
            proposal.sender_id == latest.receiver_id
            and proposal.receiver_id == latest.sender_id
        ):
            await self._close_bilateral_and_continue(
                negotiation,
                owner,
                reason=(
                    "Mediator proposal direction does not match "
                    "the live negotiation."
                ),
            )
            return True

        self.validate_outgoing(
            proposal.sender_id,
            proposal.offered_resources,
        )
        self.validate_outgoing(
            proposal.receiver_id,
            proposal.requested_resources,
        )

        message = self.privacy_guard.sanitize_message(
            sender_agent.user,
            "Counter-offer using the public mediator compromise.",
        )

        mediated_offer = counter_offer(
            negotiation=negotiation,
            previous_offer_id=latest.id,
            sender_id=proposal.sender_id,
            receiver_id=proposal.receiver_id,
            offered_resources=proposal.offered_resources,
            requested_resources=proposal.requested_resources,
            message=message,
        )

        await self._decision(
            proposal.sender_id,
            AgentDecision(
                action=AgentAction.COUNTER,
                reason=(
                    "PersonalAgent accepted the mediator compromise "
                    "and sent those public terms."
                ),
                partner_id=proposal.receiver_id,
                negotiation_id=negotiation.id,
                offer_id=mediated_offer.id,
            ),
            update_runtime=(proposal.sender_id == owner),
        )

        await self._emit(
            "counter_offer_sent",
            proposal.sender_id,
            negotiation.id,
            {
                "negotiation_id": negotiation.id,
                "offer": mediated_offer,
                "mediated": True,
                "message": (
                    "Mediator compromise was privately validated "
                    "and sent as a real counter-offer."
                ),
            },
        )

        accepted = accept_offer(
            negotiation,
            mediated_offer.id,
        )

        await self._decision(
            proposal.receiver_id,
            AgentDecision(
                action=AgentAction.ACCEPT,
                reason=(
                    "PersonalAgent privately accepted "
                    "the mediator compromise."
                ),
                partner_id=proposal.sender_id,
                negotiation_id=negotiation.id,
                offer_id=accepted.id,
            ),
            update_runtime=(proposal.receiver_id == owner),
        )

        await self._emit(
            "offer_accepted",
            proposal.receiver_id,
            negotiation.id,
            {
                "negotiation_id": negotiation.id,
                "offer": accepted,
                "mediated": True,
                "message": (
                    "Both PersonalAgents accepted "
                    "the mediator compromise."
                ),
            },
        )

        self.validate_settlement(
            negotiation
        )

        decision = (
            self.get_personal_agent(owner)
            .request_human_validation(
                negotiation
            )
        )

        await self._decision(
            owner,
            decision,
        )

        await self._emit(
            "human_approval_required",
            owner,
            negotiation.id,
            {
                "negotiation": negotiation,
                "mediated": True,
                "message": (
                    "Mediator-assisted agreement requires "
                    "human approval."
                ),
            },
        )

        await self._emit(
            "negotiation_updated",
            owner,
            negotiation.id,
            {
                "negotiation": negotiation,
                "mediated": True,
            },
        )

        await self._changed()
        return True

    async def _search_job(
        self,
        user_id: str,
        goal: ResourceRequest,
        objective_id: str | None = None,
    ) -> None:
        try:
            await asyncio.sleep(self.step_delay)
            async with self.lock:
                context = self._objectives.get(
                    objective_id or ""
                )
                if context is not None and context.cancelled:
                    return
                await self._search_coalition(
                    user_id,
                    goal,
                    None,
                    context=context,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Coalition search failed"
            )
            await self._emit(
                "error",
                user_id,
                message=(
                    "Coalition search could not complete."
                ),
            )
        finally:
            state = self._runtime.get(user_id)
            if state is not None and state.get("status") == "exhausted":
                await self._emit(
                    "agent_stopped",
                    user_id,
                    message="Coalition discovery finished with no viable alternative.",
                )
            else:
                await self._emit(
                    "coalition_search_completed",
                    user_id,
                    message="Coalition discovery step finished.",
                )

    def discover_coalitions(
        self,
        user_id: str,
        min_size: int = 3,
        max_size: int = 4,
        *,
        goal: ResourceRequest | None = None,
    ) -> list[RankedCoalition]:
        self.get_personal_agent(user_id)

        if not 3 <= min_size <= max_size <= 6:
            raise ValueError(
                "Use 3 <= min_size <= max_size <= 6 "
                "for this demo."
            )

        ranked = self.coalition_agent.discover(
            target_user_id=user_id,
            min_size=min_size,
            max_size=max_size,
            max_results=20,
        )

        feasible: list[RankedCoalition] = []

        for item in ranked:
            proposal = item.proposal

            if goal is not None:
                incoming = [
                    transfer
                    for transfer in proposal.transfers
                    if transfer.to_user_id == user_id
                ]

                if not self._satisfies(
                    goal,
                    incoming,
                ):
                    continue

            try:
                for participant_id in proposal.participant_ids:
                    participant = self.world.get_user(
                        participant_id
                    )

                    if participant is None:
                        raise ValueError(
                            "Missing coalition participant."
                        )

                    if any(
                        self.reputation.get_score(other)
                        < participant.constraints.minimum_reputation
                        for other in proposal.participant_ids
                        if other != participant_id
                    ):
                        raise ValueError(
                            "Trust policy blocks coalition."
                        )

                    outgoing = [
                        Resource(
                            resource_type=transfer.resource_type,
                            quantity=transfer.quantity,
                            unit=transfer.unit,
                        )
                        for transfer in proposal.transfers
                        if transfer.from_user_id == participant_id
                    ]

                    self.validate_outgoing(
                        participant_id,
                        outgoing,
                    )

            except ValueError:
                continue

            feasible.append(item)

        self._coalitions[user_id] = feasible
        return feasible

    async def _search_coalition(
        self,
        user_id: str,
        goal: ResourceRequest | None,
        source_id: str | None,
        *,
        context: ObjectiveContext | None = None,
    ) -> None:
        """Find, privately validate, and stage a multi-party exchange."""

        if context is not None:
            self._set_runtime(
                user_id,
                "searching_coalition",
                "Searching multi-party alternatives.",
                source_id,
                objective=context,
            )

        await self._decision(
            user_id,
            AgentDecision(
                action=AgentAction.SEARCH_COALITION,
                reason="Looking for a multi-party alternative.",
                negotiation_id=source_id,
            ),
        )

        await self._emit(
            "coalition_search_started",
            user_id,
            source_id,
            message="Searching resource-exchange cycles.",
        )

        candidates = self.discover_coalitions(
            user_id,
            goal=goal,
        )

        candidates = (
            await self
            ._choose_coalition_with_llm(
                user_id=user_id,
                candidates=candidates,
                entity_id=source_id,
            )
        )

        for candidate in candidates:
            signature = coalition_signature(candidate.proposal)

            if (
                context is not None
                and signature in context.attempted_coalitions
            ):
                continue

            if context is not None:
                context.attempted_coalitions.add(signature)

            deal = CoalitionDeal(
                id=candidate.proposal.id,
                target_user_id=user_id,
                source_negotiation_id=source_id,
                proposal=candidate.proposal.model_copy(deep=True),
                score=candidate.score,
                average_reputation=candidate.average_reputation,
                human_approvals={
                    participant_id: None
                    for participant_id in candidate.proposal.participant_ids
                },
            )

            self._coalition_deals[deal.id] = deal
            self._coalition_owner[deal.id] = user_id

            if context is not None:
                context.coalition_ids.add(deal.id)
                self._coalition_context[deal.id] = context.id
                self._set_runtime(
                    user_id,
                    "coalition_validating",
                    "PersonalAgents are privately validating a coalition proposal.",
                    deal.id,
                    objective=context,
                )

            await self._emit(
                "coalition_found",
                user_id,
                deal.id,
                {
                    "coalition": candidate,
                    "coalition_deal": deal,
                    "message": (
                        "Coalition candidate found. Each PersonalAgent will now "
                        "validate only its own private constraints."
                    ),
                },
            )

            accepted = await self._validate_coalition_agents(deal)
            if not accepted:
                continue

            deal.touch(CoalitionStatus.WAITING_HUMANS)

            if context is not None:
                self._set_runtime(
                    user_id,
                    "coalition_waiting_humans",
                    "All PersonalAgents accepted the coalition; waiting for each human participant.",
                    deal.id,
                    objective=context,
                )

            for participant_id in deal.proposal.participant_ids:
                await self._emit(
                    "coalition_human_approval_required",
                    participant_id,
                    deal.id,
                    {
                        "coalition_deal": deal,
                        "message": (
                            "Your PersonalAgent accepted this coalition. "
                            "Human approval is required before execution."
                        ),
                    },
                )

            await self._changed()
            return

        self._set_runtime(
            user_id,
            "exhausted",
            (
                "No other eligible partner or coalition is available. "
                "Change the goal or wait for market changes."
            ),
            source_id,
            objective=context,
        )

        await self._decision(
            user_id,
            AgentDecision(
                action=AgentAction.STOP,
                reason="No alternative available for this objective.",
                negotiation_id=source_id,
            ),
        )

        await self._changed()
        await self._emit(
            "agent_stopped",
            user_id,
            source_id,
            message="No eligible coalition was accepted by all PersonalAgents.",
        )

    async def _validate_coalition_agents(
        self,
        deal: CoalitionDeal,
    ) -> bool:
        """Ask every PersonalAgent to evaluate the proposal privately."""

        deal.touch(CoalitionStatus.AGENT_VALIDATING)
        accepted = True
        first_rejection: str | None = None

        for participant_id in deal.proposal.participant_ids:
            evaluation = (
                self.get_personal_agent(participant_id)
                .evaluate_coalition_proposal(deal.proposal)
            )

            deal.agent_evaluations[participant_id] = evaluation
            deal.touch()

            if not evaluation.accepted:
                accepted = False
                if first_rejection is None:
                    first_rejection = participant_id

            await self._emit(
                "coalition_agent_evaluated",
                participant_id,
                deal.id,
                {
                    "accepted": evaluation.accepted,
                    "coalition_id": deal.id,
                    "coalition_deal": deal,
                    "message": evaluation.reason,
                },
            )

        if accepted:
            await self._emit(
                "coalition_selected",
                deal.target_user_id,
                deal.id,
                {
                    "coalition_deal": deal,
                    "message": "All PersonalAgents privately accepted the coalition candidate.",
                },
            )
            return True

        deal.rejected_by = first_rejection
        deal.touch(CoalitionStatus.REJECTED)

        await self._emit(
            "coalition_rejected",
            deal.target_user_id,
            deal.id,
            {
                "coalition_deal": deal,
                "message": (
                    "At least one PersonalAgent rejected this coalition. "
                    "Searching the next coalition candidate."
                ),
            },
        )
        return False

    def coalition_snapshot(self) -> list[RankedCoalition]:
        """Legacy ranked candidates retained for discovery/graph clients."""
        return [
            item
            for items in self._coalitions.values()
            for item in items
        ]

    def coalition_deal_snapshot(self) -> list[CoalitionDeal]:
        return [
            deal.model_copy(deep=True)
            for deal in sorted(
                self._coalition_deals.values(),
                key=lambda item: item.created_at,
            )
        ]

    def get_coalition_deal(
        self,
        coalition_id: str,
    ) -> CoalitionDeal:
        deal = self._coalition_deals.get(coalition_id)
        if deal is None:
            raise ValueError("Coalition deal not found.")
        return deal

    def _coalition_context_for(
        self,
        coalition_id: str,
    ) -> ObjectiveContext | None:
        context_id = self._coalition_context.get(coalition_id)
        if context_id is None:
            return None
        return self._objectives.get(context_id)

    async def approve_coalition_by_human(
        self,
        coalition_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        async with self.lock:
            self._ensure_available()
            deal = self.get_coalition_deal(coalition_id)

            if deal.status not in {
                CoalitionStatus.WAITING_HUMANS,
                CoalitionStatus.APPROVED,
            }:
                raise AgentConflict(
                    "Coalition is not awaiting human approval."
                )

            if user_id not in deal.proposal.participant_ids:
                raise AgentConflict(
                    "User is not a participant in this coalition."
                )

            if deal.human_approvals.get(user_id) is True:
                return {
                    "message": "Coalition was already approved by this human.",
                    "coalition": deal.model_copy(deep=True),
                }

            if deal.human_approvals.get(user_id) is False:
                raise AgentConflict(
                    "This participant already rejected the coalition."
                )

            deal.human_approvals[user_id] = True
            deal.touch()

            await self._emit(
                "coalition_human_approved",
                user_id,
                deal.id,
                {
                    "coalition_deal": deal,
                    "message": "Participant approved the coalition.",
                },
            )

            all_approved = all(
                value is True
                for value in deal.human_approvals.values()
            )

            if all_approved:
                deal.touch(CoalitionStatus.APPROVED)
                owner = self._coalition_owner.get(
                    deal.id,
                    deal.target_user_id,
                )
                context = self._coalition_context_for(deal.id)
                self._set_runtime(
                    owner,
                    "coalition_approved",
                    "All human participants approved; awaiting explicit atomic execution.",
                    deal.id,
                    objective=context,
                )

                for participant_id in deal.proposal.participant_ids:
                    await self._emit(
                        "coalition_approved",
                        participant_id,
                        deal.id,
                        {
                            "coalition_deal": deal,
                            "message": "Every human participant approved the coalition.",
                        },
                    )

            await self._changed()
            return {
                "message": (
                    "All humans approved the coalition."
                    if all_approved
                    else "Coalition approval recorded."
                ),
                "coalition": deal.model_copy(deep=True),
            }

    async def reject_coalition_by_human(
        self,
        coalition_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        async with self.lock:
            self._ensure_available()
            deal = self.get_coalition_deal(coalition_id)

            if deal.status != CoalitionStatus.WAITING_HUMANS:
                raise AgentConflict(
                    "Coalition is not awaiting human approval."
                )

            if user_id not in deal.proposal.participant_ids:
                raise AgentConflict(
                    "User is not a participant in this coalition."
                )

            deal.human_approvals[user_id] = False
            deal.rejected_by = user_id
            deal.touch(CoalitionStatus.REJECTED)

            for participant_id in deal.proposal.participant_ids:
                await self._emit(
                    "coalition_human_rejected",
                    participant_id,
                    deal.id,
                    {
                        "coalition_deal": deal,
                        "message": (
                            "A human participant rejected this coalition. "
                            "No transfer was executed."
                        ),
                    },
                )

            context = self._coalition_context_for(deal.id)
            owner = self._coalition_owner.get(
                deal.id,
                deal.target_user_id,
            )

            if context is not None and not context.cancelled:
                self._set_runtime(
                    owner,
                    "searching_coalition",
                    "Coalition rejected; searching another multi-party alternative.",
                    deal.id,
                    objective=context,
                )
                await self._search_coalition(
                    owner,
                    context.request,
                    deal.source_negotiation_id,
                    context=context,
                )
            else:
                self._set_runtime(
                    owner,
                    "cancelled",
                    "Coalition rejected; no owned objective remains to continue.",
                    deal.id,
                )

            await self._changed()
            return {
                "message": "Coalition rejected; no transfers executed.",
                "coalition": deal.model_copy(deep=True),
            }

    async def execute_coalition(
        self,
        coalition_id: str,
    ) -> dict[str, Any]:
        async with self.lock:
            self._ensure_available()
            deal = self.get_coalition_deal(coalition_id)

            if deal.status != CoalitionStatus.APPROVED:
                raise AgentConflict(
                    "All human approvals are required before coalition execution."
                )

            if not all(
                value is True
                for value in deal.human_approvals.values()
            ):
                raise AgentConflict(
                    "Coalition approvals are incomplete."
                )

            feasibility = evaluate_coalition_feasibility(
                deal.proposal,
                self.world.get_users(),
            )
            if not feasibility.feasible:
                deal.touch(CoalitionStatus.REJECTED)
                await self._emit(
                    "coalition_exchange_failed",
                    deal.target_user_id,
                    deal.id,
                    {
                        "coalition_deal": deal,
                        "message": (
                            "Coalition became infeasible before execution. "
                            "No transfer was executed."
                        ),
                    },
                )
                raise AgentConflict(
                    "Coalition is no longer feasible; no transfer was executed."
                )

            for participant_id in deal.proposal.participant_ids:
                evaluation = (
                    self.get_personal_agent(participant_id)
                    .evaluate_coalition_proposal(deal.proposal)
                )
                if not evaluation.accepted:
                    deal.touch(CoalitionStatus.REJECTED)
                    deal.rejected_by = participant_id
                    await self._emit(
                        "coalition_exchange_failed",
                        participant_id,
                        deal.id,
                        {
                            "coalition_deal": deal,
                            "message": (
                                "A current private policy no longer permits the coalition. "
                                "No transfer was executed."
                            ),
                        },
                    )
                    raise AgentConflict(
                        "Coalition is no longer permitted by current agent policy."
                    )

            deal.touch(CoalitionStatus.EXECUTING)

            for participant_id in deal.proposal.participant_ids:
                await self._emit(
                    "coalition_exchange_started",
                    participant_id,
                    deal.id,
                    {
                        "coalition_deal": deal,
                        "message": "Atomic coalition execution started.",
                    },
                )

            try:
                success = execute_coalition_atomically(
                    deal.proposal,
                    self.world.users,
                )
                if success is not True:
                    raise RuntimeError(
                        "Coalition settlement engine did not confirm success."
                    )
            except Exception:
                deal.touch(CoalitionStatus.FAILED)
                logger.exception(
                    "Atomic coalition execution failed"
                )
                for participant_id in deal.proposal.participant_ids:
                    await self._emit(
                        "coalition_exchange_failed",
                        participant_id,
                        deal.id,
                        {
                            "coalition_deal": deal,
                            "message": (
                                "Atomic coalition execution failed and was rolled back. "
                                "Inspect backend logs."
                            ),
                        },
                    )
                await self._changed()
                raise

            deal.touch(CoalitionStatus.COMPLETED)

            for participant_id in deal.proposal.participant_ids:
                self.reputation.record_event(
                    participant_id,
                    ReputationEventType.TRANSACTION_SUCCESS,
                )

            context = self._coalition_context_for(deal.id)
            owner = self._coalition_owner.get(
                deal.id,
                deal.target_user_id,
            )

            if context is not None:
                context.state = "completed"
                context.cancelled = True

            self._set_runtime(
                owner,
                "completed",
                "Atomic coalition exchange completed.",
                deal.id,
                objective=context,
            )

            for participant_id in deal.proposal.participant_ids:
                await self._emit(
                    "coalition_exchange_completed",
                    participant_id,
                    deal.id,
                    {
                        "coalition_deal": deal,
                        "message": "All coalition transfers completed atomically.",
                    },
                )

            await self._changed()
            return {
                "success": True,
                "message": "Coalition exchange executed atomically.",
                "coalition": deal.model_copy(deep=True),
            }

    async def mediate_negotiation(
        self,
        negotiation: Negotiation,
    ) -> MediationResult:
        """
        Manual/advisory inspection via /mediate.

        The manual route still does not mutate the negotiation.
        Automatic application is handled by
        _attempt_automatic_mediation().
        """

        await self._emit(
            "mediation_started",
            entity_id=negotiation.id,
            message=(
                "Manual mediator inspection of "
                "already revealed offers."
            ),
        )

        result = self.mediator_agent.mediate(
            negotiation,
            trigger=MediationTrigger.MANUAL,
        )

        await self._emit(
            "mediation_suggestion",
            entity_id=negotiation.id,
            payload={
                "negotiation_id": negotiation.id,
                "result": result,
                "message": (
                    "Mediator advice only; no terms "
                    "changed through the manual route."
                ),
            },
        )

        return result

    async def _decision(
        self,
        user_id: str,
        decision: AgentDecision,
        *,
        update_runtime: bool = True,
    ) -> None:
        """Diffuse une décision sans confondre participation et mandat propriétaire.

        Un agent peut répondre à une négociation qui appartient à l'objectif
        d'un autre utilisateur. Dans ce cas, on publie bien son activité,
        mais on ne remplace pas son éventuel état runtime indépendant.
        """
        states = {
            AgentAction.SEARCH_MARKET: "searching", AgentAction.START_NEGOTIATION: "negotiating",
            AgentAction.COUNTER: "negotiating", AgentAction.ACCEPT: "negotiating",
            AgentAction.WAIT_HUMAN: "waiting_human", AgentAction.SEARCH_COALITION: "searching_coalition",
        }
        if update_runtime and decision.action in states:
            self._set_runtime(user_id, states[decision.action], {
                "searching": "Searching available alternatives.",
                "negotiating": "Negotiation in progress.",
                "waiting_human": "Waiting for human approval of this deal.",
                "searching_coalition": "Searching multi-party alternatives.",
            }[states[decision.action]], decision.negotiation_id)
        public = decision.model_dump(mode="json")
        public["reason"] = self.privacy_guard.sanitize_message(
            self.get_personal_agent(user_id).user, decision.reason,
        )
        await self._emit("agent_action", user_id, decision.negotiation_id, {"decision": public})

    async def _changed(self) -> None:
        # Met aussi à jour le snapshot utilisé par MarketGraph dans le frontend initial.
        await self._emit("market_updated", message="Reload the authoritative REST state.")

    async def _emit(
        self, event_type: str, user_id: str | None = None, entity_id: str | None = None,
        payload: dict[str, Any] | None = None, *, message: str | None = None,
    ) -> None:
        """
        Publish observational telemetry without letting the WebSocket layer
        become part of the transaction boundary.

        A disconnected client or a stale realtime event contract must never
        stop negotiation, mediation, coalition validation or settlement.
        REST remains authoritative.
        """
        data = dict(payload or {})
        if message is not None:
            data["message"] = message
        data["simulation_time"] = self.world.current_time.isoformat()
        if user_id is not None and user_id in self._runtime:
            data["agent_state"] = dict(self._runtime[user_id])

        try:
            await self.emit_event(
                event_type=event_type,
                user_id=user_id,
                entity_id=entity_id,
                payload=data,
            )
        except Exception:
            logger.exception(
                "Realtime event emission failed but business state will continue: %s",
                event_type,
            )

    def _start_worker(self, key: str, coroutine: Coroutine[Any, Any, None]) -> None:
        task = asyncio.create_task(coroutine, name=f"compute-exchange:{key}")
        self._tasks[key] = task

        def finished(done: asyncio.Task[None]) -> None:
            if self._tasks.get(key) is done:
                self._tasks.pop(key, None)
            if not done.cancelled():
                error = done.exception()
                if error is not None:
                    logger.error("Unexpected worker error", exc_info=(type(error), error, error.__traceback__))
        task.add_done_callback(finished)

    async def stop_all(self) -> None:
        """Attendre réellement l'arrêt des tâches AVANT reset/chargement d'un scénario."""
        tasks = tuple(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        self._owners.clear()
        self._goals.clear()
        self._coalitions.clear()
        self._coalition_deals.clear()
        self._coalition_context.clear()
        self._coalition_owner.clear()
        self._objectives.clear()
        self._objective_by_negotiation.clear()
        self._runtime.clear()
        self._mediation_attempted.clear()


    # ---- État réel et reprise d'un objectif après refus humain -----------------
    def _context(self, negotiation_id: str | None) -> ObjectiveContext | None:
        return self._objectives.get(self._objective_by_negotiation.get(negotiation_id or "", ""))

    def runtime_snapshot(self) -> list[dict[str, Any]]:
        return [dict(state) for state in self._runtime.values()]

    def _set_runtime(
        self, user_id: str, status: str, reason: str,
        negotiation_id: str | None = None, *, objective: ObjectiveContext | None = None,
    ) -> None:
        context = objective or self._context(negotiation_id)
        if context is not None and context.user_id == user_id:
            context.state = status
        self._runtime[user_id] = {
            "user_id": user_id, "status": status, "reason": reason,
            "negotiation_id": negotiation_id,
            "objective_id": context.id if context is not None and context.user_id == user_id else None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def mark_deal_state(self, negotiation_id: str, status: str) -> None:
        """Appelé sous world_lock par les commandes humaines de l'API."""
        owner = self._owners.get(negotiation_id)
        if owner is not None:
            self._set_runtime(owner, status, {
                "approved": "Approved by the human; awaiting explicit execution.",
                "completed": "Exchange completed.",
                "cancelled": "Objective stopped by the human.",
            }.get(status, "Deal state changed."), negotiation_id)
        context = self._context(negotiation_id)
        if context is not None and status in {"completed", "cancelled"}:
            context.cancelled = True

    def _attach_attempt(self, context: ObjectiveContext, result: AgentStepResult) -> None:
        if result.negotiation is None or result.offer is None:
            raise ValueError("An alternative must create a new bilateral offer.")
        identifier = result.negotiation.id
        context.negotiation_ids.add(identifier)
        context.attempted.add(result.offer.receiver_id)
        self._objective_by_negotiation[identifier] = context.id
        self._owners[identifier] = context.user_id
        self._goals[identifier] = context.request.model_copy(deep=True)
        self._set_runtime(context.user_id, "negotiating", "Negotiation in progress.", identifier, objective=context)

    async def reject_by_human(self, negotiation_id: str, *, continue_search: bool = True) -> dict:
        """Refuse définitivement le deal ; le mandat peut chercher un AUTRE partenaire.

        Aucun nouveau mandat n'est inféré pour une négociation manuelle sans objectif.
        Exclusions locales à cet objectif, jamais ajoutées à User.blocked_partners.
        """
        async with self.lock:
            self._ensure_available()
            negotiation = self.world.active_negotiations.get(negotiation_id)
            if negotiation is None or negotiation.status not in OPEN_DEAL:
                raise AgentConflict("Deal already closed or executed.")
            context = self._context(negotiation_id)
            reject_negotiation(negotiation)
            task = self._tasks.get(negotiation_id)
            if task is not None and not task.done():
                task.cancel()
            retry = continue_search and context is not None and not context.cancelled
            owner = self._owners.get(negotiation_id)
            if owner is not None:
                self._set_runtime(owner, "searching" if retry else "cancelled",
                    "Deal rejected. Looking for a different alternative." if retry else "Deal rejected; no automatic continuation.",
                    negotiation_id, objective=context)
            if context is not None and not retry:
                context.cancelled = True
            await self._emit("human_rejected", owner, negotiation_id, {
                "negotiation": negotiation, "negotiation_id": negotiation_id,
                "message": "Human rejected this deal. It will not be reopened.",
                "retry_scheduled": retry,
            })

            # Tous les autres participants sont explicitement informés.
            # Leur propre objectif indépendant n'est ni annulé ni modifié.
            notified_participants = [
                participant_id
                for participant_id in negotiation.participant_ids
                if participant_id != owner
            ] if owner is not None else list(negotiation.participant_ids)

            for participant_id in notified_participants:
                stale = self._runtime.get(participant_id)
                if (
                    stale is not None
                    and stale.get("negotiation_id") == negotiation_id
                    and stale.get("objective_id") is None
                ):
                    # Nettoyage des anciens états transitoires créés par les
                    # versions précédentes de l'orchestrateur.
                    self._runtime.pop(participant_id, None)

                await self._emit("agent_notified", participant_id, negotiation_id, {
                    "negotiation_id": negotiation_id,
                    "message": (
                        "The human reviewer rejected this proposed deal. "
                        "This negotiation is closed; any independent objective remains active."
                    ),
                })

            if retry:
                await self._schedule_alternative(context, negotiation_id)
            await self._changed()
            return {"message": "Deal rejected; searching alternatives." if retry else "Deal rejected.",
                    "negotiation": negotiation.model_copy(deep=True), "retry_scheduled": retry}

    async def _schedule_alternative(self, context: ObjectiveContext, previous_id: str) -> None:
        if context.cancelled or self.maintenance:
            return
        self._set_runtime(context.user_id, "searching", "Looking for an untried partner for the same objective.", previous_id, objective=context)
        await self._decision(context.user_id, AgentDecision(
            action=AgentAction.SEARCH_MARKET,
            reason="Previous deal closed. Searching a different partner without changing private constraints.",
            negotiation_id=previous_id,
        ))
        key = f"retry:{context.id}"
        if not self.is_running(key):
            self._start_worker(key, self._retry_job(context.id, previous_id))

    async def _retry_job(self, objective_id: str, previous_id: str) -> None:
        try:
            await asyncio.sleep(self.step_delay)
            async with self.lock:
                context = self._objectives.get(objective_id)
                if context is None or context.cancelled or self.maintenance:
                    return
                self.validate_outgoing(context.user_id, context.offered_resources)
                if context.request.deadline is not None and context.request.deadline <= self.world.current_time:
                    context.state = "exhausted"
                    self._set_runtime(context.user_id, "exhausted", "Objective deadline reached; no new offer sent.", previous_id, objective=context)
                    await self._emit("agent_stopped", context.user_id, previous_id, message="Objective deadline reached.")
                    await self._changed()
                    return
                agent = self.get_personal_agent(context.user_id)
                candidates = [
                    candidate
                    for candidate
                    in agent.discover_candidates(
                        context.request.resource_type
                    )
                    if candidate.user_id
                    not in context.attempted
                ]

                while (
                    candidates
                    and len(context.attempted)
                    < self.max_partner_attempts
                ):
                    candidate = (
                        await self
                        ._choose_partner_with_llm(
                            agent=agent,
                            resource_type=(
                                context.request
                                .resource_type
                            ),
                            candidates=candidates,
                            entity_id=previous_id,
                        )
                    )

                    context.attempted.add(
                        candidate.user_id
                    )
                    candidates = [
                        item
                        for item in candidates
                        if item.user_id
                        != candidate.user_id
                    ]

                    try:
                        opening = (
                            await self
                            ._choose_initial_offer_with_llm(
                                agent=agent,
                                partner=candidate,
                                authorized_offered_resources=[
                                    r.model_copy(deep=True)
                                    for r
                                    in context.offered_resources
                                ],
                                request=(
                                    context.request
                                    .model_copy(deep=True)
                                ),
                                entity_id=previous_id,
                            )
                        )

                        result = agent.start_negotiation(
                            partner_id=candidate.user_id,
                            offered_resources=[
                                r.model_copy(deep=True)
                                for r
                                in opening.offered_resources
                            ],
                            requested_resources=[
                                r.model_copy(deep=True)
                                for r
                                in opening.requested_resources
                            ],
                            message=context.message,
                        )
                    except ValueError:
                        logger.info("Alternative disallowed for objective %s", context.id)
                        continue

                    self._attach_attempt(context, result)
                    identifier = result.negotiation.id
                    await self._emit("provider_found", context.user_id, identifier, {
                        "provider_id": candidate.user_id,
                        "reputation": candidate.reputation,
                        "message": "A different eligible provider was selected.",
                    })
                    await self._decision(context.user_id, result.decision)
                    await self._emit("negotiation_started", context.user_id, identifier, {
                        "negotiation": result.negotiation, "previous_negotiation_id": previous_id,
                        "message": "New alternative negotiation; the rejected deal stays closed.",
                    })
                    await self._emit("offer_sent", context.user_id, identifier, {
                        "negotiation_id": identifier, "offer": result.offer,
                        "message": "Offer sent to the new partner.",
                    })
                    self._start_worker(identifier, self._run(identifier, context.user_id))
                    await self._changed()
                    return
                # Les coalitions constituent des termes différents, pas une réactivation du deal.
                await self._search_coalition(context.user_id, context.request, previous_id, context=context)
                await self._changed()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Alternative search failed for objective %s", objective_id)
            async with self.lock:
                context = self._objectives.get(objective_id)
                if context is not None and not context.cancelled:
                    self._set_runtime(context.user_id, "failed", "Alternative search failed safely; inspect backend logs.", previous_id, objective=context)
                    await self._emit("error", context.user_id, previous_id, message="Alternative search failed safely.")
                    await self._changed()

    async def stop_user(self, user_id: str) -> dict:
        """Arrêt explicite d'un objectif réellement détenu par cet utilisateur.

        Répondre à l'offre d'un autre utilisateur ne crée pas un mandat
        propriétaire. Cliquer Stop sur un agent sans objectif actif devient
        donc un no-op au lieu de le marquer artificiellement CANCELLED.
        """
        tasks: list[asyncio.Task[None]] = []
        async with self.lock:
            self._ensure_available()
            self.get_personal_agent(user_id)

            active_contexts = [
                context
                for context in self._objectives.values()
                if (
                    context.user_id == user_id
                    and not context.cancelled
                    and context.state in {
                        "searching", "negotiating", "waiting_human",
                        "approved", "searching_coalition", "coalition_proposed",
                        "coalition_validating", "coalition_waiting_humans",
                        "coalition_approved",
                    }
                )
            ]

            if not active_contexts:
                # Retirer seulement un éventuel ancien état transitoire sans
                # fabriquer un faux état CANCELLED.
                state = self._runtime.get(user_id)
                if state is not None and state.get("objective_id") is None:
                    self._runtime.pop(user_id, None)
                return {
                    "message": "No active owned objective to stop.",
                    "user_id": user_id,
                    "stopped": False,
                }

            for context in active_contexts:
                context.cancelled = True
                context.state = "cancelled"
                for identifier in context.negotiation_ids:
                    negotiation = self.world.active_negotiations.get(identifier)
                    if negotiation is not None and negotiation.status in OPEN_DEAL:
                        cancel_negotiation(negotiation)
                        await self._emit(
                            "negotiation_updated",
                            user_id,
                            identifier,
                            {"negotiation": negotiation},
                        )
                for coalition_id in context.coalition_ids:
                    deal = self._coalition_deals.get(coalition_id)
                    if deal is not None and deal.status in {
                        CoalitionStatus.AGENT_VALIDATING,
                        CoalitionStatus.WAITING_HUMANS,
                        CoalitionStatus.APPROVED,
                    }:
                        deal.touch(CoalitionStatus.CANCELLED)
                        await self._emit(
                            "coalition_cancelled",
                            user_id,
                            coalition_id,
                            {
                                "coalition_deal": deal,
                                "message": "Coalition objective stopped before execution.",
                            },
                        )
                keys = context.negotiation_ids | {f"retry:{context.id}", f"search:{user_id}"}
                for key in keys:
                    task = self._tasks.get(key)
                    if task is not None and not task.done():
                        task.cancel()
                        tasks.append(task)

            self._set_runtime(
                user_id,
                "cancelled",
                "Objective stopped by the human; no further offers will be sent.",
                objective=active_contexts[-1],
            )
            await self._emit(
                "agent_stopped",
                user_id,
                message="Owned objective stopped by the human.",
            )
            await self._changed()

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        return {
            "message": "Objective stopped.",
            "user_id": user_id,
            "stopped": True,
        }

