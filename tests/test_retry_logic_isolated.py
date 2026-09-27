"""Tests ciblés de l'orchestrateur, avec agents/modèles factices explicites.

Ne teste PAS les vrais PersonalAgent, PrivacyGuard, le settlement ni FastAPI.
Le code exécuté de l'orchestrateur est celui du projet ; ses dépendances sont
substituées pour isoler annulation, reprise, routage et bornage de recherche.
"""
import ast
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from enum import Enum

import pytest
from pydantic import BaseModel, Field

Status = Enum('Status', {key.upper(): key for key in ['open', 'negotiating', 'agreement_found',
    'waiting_human', 'approved', 'rejected', 'cancelled', 'failed']}, type=str)
OfferStatus = Enum('OfferStatus', {key.upper(): key for key in ['pending', 'accepted', 'rejected',
    'countered', 'expired', 'cancelled']}, type=str)
Action = Enum('Action', {key.upper(): key for key in ['search_market', 'start_negotiation',
    'accept', 'counter', 'reject', 'search_coalition', 'wait_human', 'stop']}, type=str)

class Resource(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    resource_type: str
    quantity: float
    unit: str
    deadline: datetime | None = None

class Offer(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    sender_id: str
    receiver_id: str
    offered_resources: list[Resource]
    requested_resources: list[Resource]
    message: str | None = None
    status: OfferStatus = OfferStatus.PENDING
    def is_expired(self): return False

class Negotiation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    participant_ids: list[str]
    offers: list[Offer]
    status: Status = Status.NEGOTIATING
    max_rounds: int = 10
    accepted_offer_id: str | None = None
    def get_last_offer(self): return self.offers[-1] if self.offers else None
    def get_offer(self, identifier): return next((o for o in self.offers if o.id == identifier), None)
    def fail(self): self.status = Status.FAILED

class Decision(BaseModel):
    action: Action
    reason: str
    partner_id: str | None = None
    negotiation_id: str | None = None
    offer_id: str | None = None

class Step(BaseModel):
    decision: Decision
    negotiation: Negotiation | None = None
    offer: Offer | None = None

class World:
    def __init__(self):
        self.current_time = datetime.now(timezone.utc)
        self.users = {}
        self.active_negotiations = {}
        self.completed_negotiations = {}
    def get_user(self, identifier): return self.users.get(identifier)
    def get_negotiation(self, identifier): return self.active_negotiations.get(identifier)

class FakeGuard:
    def sanitize_message(self, user, message): return message
    def check_offer(self, *args, **kwargs): return SimpleNamespace(action='allow')
class FakeReputation:
    def get_score(self, user): return 0.8
class FakeCoalitionAgent:
    def __init__(self, **kwargs): pass
    def discover(self, **kwargs): return []
class FakeMediator:
    def mediate(self, negotiation): return SimpleNamespace(action='no_action')

class FakeAgent:
    def __init__(self, *, user_id, world, reputation, privacy_guard):
        self.user_id, self.world = user_id, world
    @property
    def user(self): return self.world.get_user(self.user_id)
    def discover_candidates(self, resource_type):
        return [SimpleNamespace(user_id=u.id) for u in self.world.users.values()
                if u.id != self.user_id and u.online and any(r.resource_type == resource_type for r in u.resources)]
    def pursue_request(self, request, offered_resources, message):
        candidates = self.discover_candidates(request.resource_type)
        if not candidates: return Step(decision=Decision(action=Action.SEARCH_COALITION, reason='Search coalition'))
        return self.start_negotiation(partner_id=candidates[0].user_id, offered_resources=offered_resources,
            requested_resources=[request], message=message)
    def start_negotiation(self, *, partner_id, offered_resources, requested_resources, message):
        offer = Offer(sender_id=self.user_id, receiver_id=partner_id,
            offered_resources=offered_resources, requested_resources=requested_resources, message=message)
        negotiation = Negotiation(participant_ids=[self.user_id, partner_id], offers=[offer])
        self.world.active_negotiations[negotiation.id] = negotiation
        return Step(decision=Decision(action=Action.START_NEGOTIATION, reason='Started', partner_id=partner_id,
            negotiation_id=negotiation.id, offer_id=offer.id), negotiation=negotiation, offer=offer)
    def handle_offer(self, negotiation, offer):
        offer.status = OfferStatus.ACCEPTED
        negotiation.accepted_offer_id = offer.id
        negotiation.status = Status.AGREEMENT_FOUND
        return Step(decision=Decision(action=Action.ACCEPT, reason='Accepted', negotiation_id=negotiation.id),
            negotiation=negotiation, offer=offer)
    def request_human_validation(self, negotiation):
        negotiation.status = Status.WAITING_HUMAN
        return Decision(action=Action.WAIT_HUMAN, reason='Needs human approval', negotiation_id=negotiation.id)


def load_orchestrator():
    source = Path(__file__).resolve().parents[1] / 'app/agents/orchestrator.py'
    tree = ast.parse(source.read_text())
    tree.body = [n for n in tree.body if not (isinstance(n, ast.ImportFrom) and (n.module or '').startswith('app.'))]
    scope = dict(__name__=__name__, CoalitionAgent=FakeCoalitionAgent, RankedCoalition=object,
        MediatorAgent=FakeMediator, MediationResult=object, PersonalAgent=FakeAgent,
        AgentAction=Action, AgentDecision=Decision, AgentStepResult=Step,
        Negotiation=Negotiation, NegotiationStatus=Status, Offer=Offer, OfferStatus=OfferStatus,
        Resource=Resource, ResourceRequest=Resource, PrivacyGuard=FakeGuard,
        PrivacyAction=SimpleNamespace(BLOCK='block'), ReputationManager=FakeReputation, SimulationWorld=World,
        reject_negotiation=lambda n: setattr(n, 'status', Status.REJECTED),
        cancel_negotiation=lambda n: setattr(n, 'status', Status.CANCELLED))
    exec(compile(tree, str(source), 'exec'), scope)
    return scope

async def fixture(provider_count=2):
    scope = load_orchestrator()
    world = World()
    # Identifiants volontairement sans rapport avec les prénoms de la démo.
    owner = 'organization-701'
    def user(identifier, resources):
        return SimpleNamespace(id=identifier, online=True, resources=resources,
            constraints=SimpleNamespace(max_quantity_to_give={}, minimum_reputation=0.0), blocked_partners=[])
    world.users[owner] = user(owner, [Resource(resource_type='STORAGE', quantity=40, unit='TB-day')])
    for i in range(provider_count):
        identifier = f'provider-{i}'
        world.users[identifier] = user(identifier, [Resource(resource_type='H100', quantity=20, unit='gpu-hour')])
    events = []
    async def emit(**event): events.append(event)
    orch = scope['AgentOrchestrator'](world=world, reputation=FakeReputation(), privacy_guard=FakeGuard(),
        personal_agents={}, emit_event=emit, step_delay=0.005)
    request = Resource(resource_type='H100', quantity=8, unit='gpu-hour')
    offered = [Resource(resource_type='STORAGE', quantity=10, unit='TB-day')]
    result = await orch.pursue(user_id=owner, request=request, offered_resources=offered)
    return orch, world, owner, result.negotiation.id, events, scope

async def until(predicate):
    for _ in range(200):
        if predicate(): return
        await asyncio.sleep(0.005)
    raise AssertionError('Condition not reached')


def test_rejection_creates_different_deal_and_keeps_old_rejected():
    async def run():
        o,w,user,old,events,_ = await fixture()
        try:
            await until(lambda: w.get_negotiation(old).status == Status.WAITING_HUMAN)
            response = await o.reject_by_human(old)
            assert response['retry_scheduled'] is True
            await until(lambda: len(w.active_negotiations) == 2)
            new = next(n for n in w.active_negotiations.values() if n.id != old)
            await until(lambda: new.status == Status.WAITING_HUMAN)
            assert w.get_negotiation(old).status == Status.REJECTED
            assert new.get_last_offer().receiver_id == 'provider-1'
            assert o.runtime_snapshot()[0]['status'] in {'waiting_human','negotiating'}
            assert w.users[user].blocked_partners == []
            assert w.users[user].resources[0].quantity == 40
            assert not any(e['event_type'] == 'exchange_completed' for e in events)
            assert all('offered_resources' not in s for s in o.runtime_snapshot())
        finally: await o.stop_all()
    asyncio.run(run())


def test_no_alternative_is_reported_not_waiting_forever():
    async def run():
        o,w,user,old,_,_ = await fixture(1)
        try:
            await until(lambda: w.get_negotiation(old).status == Status.WAITING_HUMAN)
            await o.reject_by_human(old)
            await until(lambda: o._runtime[user]['status'] == 'exhausted')
            assert len(w.active_negotiations) == 1
            assert w.get_negotiation(old).status == Status.REJECTED
        finally: await o.stop_all()
    asyncio.run(run())


def test_duplicate_rejection_does_not_create_duplicate_search():
    async def run():
        o,w,user,old,_,scope = await fixture()
        try:
            await until(lambda: w.get_negotiation(old).status == Status.WAITING_HUMAN)
            await o.reject_by_human(old)
            with pytest.raises(scope['AgentConflict']): await o.reject_by_human(old)
            await until(lambda: len(w.active_negotiations) == 2)
            assert len(w.active_negotiations) == 2
        finally: await o.stop_all()
    asyncio.run(run())


def test_stop_after_rejection_cancels_scheduled_search():
    async def run():
        o,w,user,old,_,_ = await fixture()
        try:
            await until(lambda: w.get_negotiation(old).status == Status.WAITING_HUMAN)
            o.step_delay = 0.15
            await o.reject_by_human(old)
            await o.stop_user(user)
            await asyncio.sleep(0.2)
            assert len(w.active_negotiations) == 1
            assert o._runtime[user]['status'] == 'cancelled'
        finally: await o.stop_all()
    asyncio.run(run())


def test_reject_without_continuation_and_deadline():
    async def run():
        o,w,user,old,_,_ = await fixture()
        try:
            await until(lambda: w.get_negotiation(old).status == Status.WAITING_HUMAN)
            assert (await o.reject_by_human(old, continue_search=False))['retry_scheduled'] is False
            assert o._runtime[user]['status'] == 'cancelled'
            assert len(w.active_negotiations) == 1
        finally: await o.stop_all()
    asyncio.run(run())


def test_retries_are_bounded_and_reset_erases_private_contexts():
    async def run():
        o,w,user,old,_,_ = await fixture(4)
        try:
            o.max_partner_attempts = 2
            await until(lambda: w.get_negotiation(old).status == Status.WAITING_HUMAN)
            await o.reject_by_human(old)
            await until(lambda: len(w.active_negotiations) == 2)
            new = next(n for n in w.active_negotiations.values() if n.id != old)
            await until(lambda: new.status == Status.WAITING_HUMAN)
            await o.reject_by_human(new.id)
            await until(lambda: o._runtime[user]['status'] == 'exhausted')
            assert len(w.active_negotiations) == 2
        finally: await o.stop_all()
        assert o.runtime_snapshot() == [] and o._objectives == {}
    asyncio.run(run())
