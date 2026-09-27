"""Charge les JSON de scenarios/ sans coder en dur d'utilisateurs ni de résultats.

Les champs demo/expected_coalition décrivent des attentes : ils ne pilotent
jamais les décisions des agents. Validation et préparation précèdent le reset.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.models.resource import Resource, ResourceRequest
from app.models.user import User
from app.privacy import PrivacyGuard
from app.reputation.reputation import ReputationManager, ReputationRecord
from app.simulation.events import MarketEvent
from app.simulation.world import SimulationWorld
from app.tools.negotiation_tools import create_negotiation, send_offer, counter_offer


class ReputationSeed(BaseModel):
    successful_transactions: int = Field(default=0, ge=0)
    failed_transactions: int = Field(default=0, ge=0)
    cancelled_transactions: int = Field(default=0, ge=0)
    delivered_on_time: int = Field(default=0, ge=0)
    delivered_late: int = Field(default=0, ge=0)


class ScenarioGoal(BaseModel):
    user_id: str
    request: ResourceRequest
    offered_resources: list[Resource] = Field(min_length=1)
    message: str | None = None


class SeedOffer(BaseModel):
    sender_id: str
    receiver_id: str
    offered_resources: list[Resource] = Field(min_length=1)
    requested_resources: list[ResourceRequest] = Field(min_length=1)
    message: str | None = None


class SeedNegotiation(BaseModel):
    participants: list[str] = Field(min_length=2, max_length=2)
    offers: list[SeedOffer] = Field(default_factory=list, min_length=1)
    max_rounds: int = Field(default=10, ge=1, le=100)


class ScenarioDefinition(BaseModel):
    name: str
    description: str
    start_time: datetime
    users: list[User] = Field(min_length=1)
    reputation_seed: dict[str, ReputationSeed] = Field(default_factory=dict)
    goal: ScenarioGoal | None = None
    events: list[MarketEvent] = Field(default_factory=list)
    seed_negotiation: SeedNegotiation | None = None
    expected_coalition: dict[str, Any] | None = None
    privacy_demo: dict[str, Any] | None = None
    demo: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_references(self) -> ScenarioDefinition:
        if self.start_time.tzinfo is None or self.start_time.utcoffset() is None:
            raise ValueError("Scenario start_time must include a timezone.")
        ids = [user.id for user in self.users]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate scenario user IDs.")
        users = set(ids)
        for user in self.users:
            for items in (user.resources, user.needs):
                item_ids = [item.id for item in items]
                if len(item_ids) != len(set(item_ids)):
                    raise ValueError("Duplicate resource/need ID in a user inventory.")
        if set(self.reputation_seed) - users:
            raise ValueError("Reputation seed references an unknown user.")
        if self.goal is not None and self.goal.user_id not in users:
            raise ValueError("Goal references an unknown user.")
        event_ids: set[str] = set()
        for event in self.events:
            if event.user_id not in users:
                raise ValueError("Event references an unknown user.")
            if event.scheduled_at < self.start_time:
                raise ValueError("Event is scheduled before scenario start_time.")
            if event.id in event_ids:
                raise ValueError("Duplicate event ID.")
            event_ids.add(event.id)
        seed = self.seed_negotiation
        if seed is not None:
            if len(set(seed.participants)) != 2 or set(seed.participants) - users:
                raise ValueError("Invalid seeded negotiation participants.")
            if len(seed.offers) > seed.max_rounds:
                raise ValueError("Too many seeded offers for max_rounds.")
            previous: SeedOffer | None = None
            for offer in seed.offers:
                if {offer.sender_id, offer.receiver_id} != set(seed.participants):
                    raise ValueError("Invalid seeded offer participants.")
                if previous is not None and (
                    offer.sender_id != previous.receiver_id or offer.receiver_id != previous.sender_id
                ):
                    raise ValueError("Seed counter-offers must reverse sender and receiver.")
                previous = offer
        return self


def default_scenarios_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "scenarios"


def load_scenario(name: str, scenarios_dir: Path | None = None) -> ScenarioDefinition:
    if re.fullmatch(r"[A-Za-z0-9_-]+(?:\.json)?", name) is None:
        raise ValueError("Invalid scenario name. Use a filename without directories.")
    directory = (scenarios_dir or default_scenarios_dir()).resolve()
    path = (directory / f"{name.removesuffix('.json')}.json").resolve()
    if path.parent != directory:
        raise ValueError("Scenario file resolves outside scenarios/.")
    if not path.is_file():
        raise FileNotFoundError("Scenario not found.")
    return ScenarioDefinition.model_validate(json.loads(path.read_text(encoding="utf-8")))


def list_scenarios(scenarios_dir: Path | None = None) -> list[str]:
    directory = (scenarios_dir or default_scenarios_dir()).resolve()
    if not directory.is_dir():
        return []
    return sorted(path.stem for path in directory.glob("*.json")
                  if path.is_file() and path.resolve().parent == directory)


@dataclass
class PreparedScenario:
    definition: ScenarioDefinition
    world: SimulationWorld
    reputation_records: list[ReputationRecord]
    seeded_negotiation_id: str | None


def prepare_scenario(scenario: ScenarioDefinition, privacy_guard: PrivacyGuard) -> PreparedScenario:
    """Construit un état temporaire. Aucun changement dans le monde live en cas d'erreur."""
    stage = SimulationWorld(start_time=scenario.start_time)
    reputation_records: list[ReputationRecord] = []
    for user in scenario.users:
        stage.add_user(user.model_copy(deep=True))
        seed = scenario.reputation_seed.get(user.id, ReputationSeed())
        reputation_records.append(ReputationRecord(user_id=user.id, **seed.model_dump()))
    for event in scenario.events:
        stage.schedule_event(event.model_copy(deep=True))

    seeded_id = None
    seed = scenario.seed_negotiation
    if seed is not None:
        negotiation = create_negotiation(seed.participants, seed.max_rounds)
        stage.add_negotiation(negotiation)
        seeded_id = negotiation.id
        previous = None
        for item in seed.offers:
            sender = stage.get_user(item.sender_id)
            message = None if item.message is None else privacy_guard.sanitize_message(sender, item.message)
            kwargs = dict(
                negotiation=negotiation, sender_id=item.sender_id, receiver_id=item.receiver_id,
                offered_resources=[r.model_copy(deep=True) for r in item.offered_resources],
                requested_resources=[r.model_copy(deep=True) for r in item.requested_resources],
                message=message,
            )
            if previous is None:
                previous = send_offer(**kwargs)
            else:
                previous = counter_offer(previous_offer_id=previous.id, **kwargs)
    return PreparedScenario(scenario, stage, reputation_records, seeded_id)


def apply_prepared_scenario(
    prepared: PreparedScenario, *, world: SimulationWorld,
    reputation: ReputationManager, personal_agents: dict[str, Any],
) -> None:
    """Appeler SOUS le verrou du monde, APRÈS avoir attendu l'arrêt des agents.

    Le world et le gestionnaire de réputation restent les mêmes objets.
    La queue privée est adaptée ici car SimulationWorld n'expose pas de reset public.
    """
    stage = prepared.world
    reputation.replace_records(prepared.reputation_records)
    personal_agents.clear()
    world.users.clear()
    world.users.update(stage.users)
    world.registry = stage.registry
    world.active_negotiations.clear()
    world.active_negotiations.update(stage.active_negotiations)
    world.completed_negotiations.clear()
    world.current_time = stage.current_time
    world._event_queue.clear()
    world._event_queue.extend(stage._event_queue)
    world._event_counter = stage._event_counter
    world.event_history.clear()
