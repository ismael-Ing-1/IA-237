# app/tools/coalition_tools.py

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

import networkx as nx

from pydantic import BaseModel, Field

from app.models.user import User


class CoalitionTransfer(BaseModel):
    """
    Ressource transférée entre deux membres d'une coalition.
    """

    from_user_id: str
    to_user_id: str

    resource_type: str
    quantity: float
    unit: str


class CoalitionProposal(BaseModel):
    """
    Proposition d'échange multi-utilisateurs.

    Exemple :

        Alice -> Charlie : STORAGE
        Charlie -> Bob   : A100
        Bob -> Alice     : H100
    """

    id: str = Field(
        default_factory=lambda: str(uuid4())
    )

    participant_ids: list[str]

    transfers: list[CoalitionTransfer]


class CoalitionFeasibility(BaseModel):
    """
    Résultat de la validation d'une coalition.
    """

    feasible: bool

    reasons: list[str] = Field(
        default_factory=list
    )



class CoalitionStatus(str, Enum):
    """Lifecycle of an executable coalition."""

    AGENT_VALIDATING = "agent_validating"
    WAITING_HUMANS = "waiting_humans"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class CoalitionAgentEvaluation(BaseModel):
    """Public-safe verdict emitted by one PersonalAgent."""

    user_id: str
    accepted: bool
    reason: str


class CoalitionDeal(BaseModel):
    """
    Executable coalition state.

    The proposal is public. Private limits stay inside each PersonalAgent;
    only the resulting accept/reject verdict is stored here.
    """

    id: str
    target_user_id: str
    source_negotiation_id: str | None = None
    proposal: CoalitionProposal
    score: float
    average_reputation: float
    status: CoalitionStatus = CoalitionStatus.AGENT_VALIDATING
    agent_evaluations: dict[str, CoalitionAgentEvaluation] = Field(default_factory=dict)
    human_approvals: dict[str, bool | None] = Field(default_factory=dict)
    rejected_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self, status: CoalitionStatus | None = None) -> None:
        if status is not None:
            self.status = status
        self.updated_at = datetime.now(timezone.utc)


def coalition_signature(proposal: CoalitionProposal) -> str:
    """Stable identity for retries even when a new proposal UUID is generated."""

    transfers = sorted(
        (
            transfer.from_user_id,
            transfer.to_user_id,
            transfer.resource_type,
            transfer.unit,
            round(float(transfer.quantity), 9),
        )
        for transfer in proposal.transfers
    )

    return "|".join(
        f"{source}>{target}:{resource}:{unit}:{quantity}"
        for source, target, resource, unit, quantity in transfers
    )

def _find_possible_transfers(
    provider: User,
    requester: User
) -> list[CoalitionTransfer]:
    """
    Retourne toutes les ressources que provider peut fournir
    pour satisfaire complètement un besoin de requester.

    Pour le MVP, on exige que le provider puisse satisfaire
    entièrement le besoin.
    """

    transfers: list[CoalitionTransfer] = []

    for need in requester.needs:

        matching_resources = [
            resource
            for resource in provider.resources

            if (
                resource.resource_type
                == need.resource_type

                and resource.unit
                == need.unit
            )
        ]

        available_quantity = sum(
            resource.quantity
            for resource in matching_resources
        )

        if available_quantity < need.quantity:
            continue

        transfers.append(
            CoalitionTransfer(
                from_user_id=provider.id,
                to_user_id=requester.id,

                resource_type=need.resource_type,
                quantity=need.quantity,
                unit=need.unit
            )
        )

    return transfers


def build_exchange_graph(
    users: list[User]
) -> nx.DiGraph:
    """
    Construit le graphe des échanges potentiels.

    Une arête :

        A -> B

    existe si A peut satisfaire au moins un besoin de B.
    """

    graph = nx.DiGraph()

    for user in users:

        graph.add_node(
            user.id
        )

    for provider in users:

        if not provider.online:
            continue

        for requester in users:

            if provider.id == requester.id:
                continue

            if not requester.online:
                continue

            if (
                requester.id
                in provider.blocked_partners
            ):
                continue

            if (
                provider.id
                in requester.blocked_partners
            ):
                continue

            possible_transfers = (
                _find_possible_transfers(
                    provider,
                    requester
                )
            )

            if possible_transfers:

                graph.add_edge(
                    provider.id,
                    requester.id,

                    transfers=possible_transfers
                )

    return graph


def _canonical_cycle(
    cycle: list[str]
) -> tuple[str, ...]:
    """
    Deux cycles comme :

        A -> B -> C
        B -> C -> A

    représentent la même coalition.

    Cette fonction crée une représentation canonique
    pour éliminer les doublons.
    """

    rotations = []

    for i in range(len(cycle)):

        rotated = (
            cycle[i:]
            + cycle[:i]
        )

        rotations.append(
            tuple(rotated)
        )

    return min(rotations)


def find_exchange_cycles(
    users: list[User],
    min_size: int = 3,
    max_size: int = 4,
    target_user_id: str | None = None,
    max_results: int = 20
) -> list[list[str]]:
    """
    Recherche des cycles d'échange.

    Exemple :

        Alice -> Charlie
        Charlie -> Bob
        Bob -> Alice

    min_size=3 évite de retourner les simples échanges
    bilatéraux.
    """

    graph = build_exchange_graph(
        users
    )

    cycles: list[list[str]] = []

    seen: set[tuple[str, ...]] = set()

    for cycle in nx.simple_cycles(graph):

        if len(cycle) < min_size:
            continue

        if len(cycle) > max_size:
            continue

        if (
            target_user_id is not None
            and target_user_id not in cycle
        ):
            continue

        canonical = _canonical_cycle(
            cycle
        )

        if canonical in seen:
            continue

        seen.add(canonical)

        cycles.append(
            list(canonical)
        )

        if len(cycles) >= max_results:
            break

    return cycles


def build_coalition_proposal(
    cycle: list[str],
    users: list[User]
) -> CoalitionProposal:
    """
    Transforme un cycle en proposition concrète.

    Pour chaque :

        A -> B

    on choisit le premier transfert valide identifié.

    Plus tard, un CoalitionAgent pourra décider quel transfert
    est le plus intéressant.
    """

    if len(cycle) < 3:
        raise ValueError(
            "Une coalition doit contenir au moins 3 utilisateurs."
        )

    user_by_id = {
        user.id: user
        for user in users
    }

    transfers: list[CoalitionTransfer] = []

    for index, provider_id in enumerate(cycle):

        requester_id = cycle[
            (index + 1) % len(cycle)
        ]

        provider = user_by_id.get(
            provider_id
        )

        requester = user_by_id.get(
            requester_id
        )

        if provider is None or requester is None:

            raise ValueError(
                "Un utilisateur du cycle est introuvable."
            )

        possible_transfers = (
            _find_possible_transfers(
                provider,
                requester
            )
        )

        if not possible_transfers:

            raise ValueError(
                f"Aucun transfert valide entre "
                f"{provider_id} et {requester_id}."
            )

        # MVP :
        # on prend le premier transfert possible.
        transfers.append(
            possible_transfers[0]
        )

    return CoalitionProposal(
        participant_ids=cycle,
        transfers=transfers
    )


def evaluate_coalition_feasibility(
    proposal: CoalitionProposal,
    users: list[User]
) -> CoalitionFeasibility:
    """
    Vérifie qu'une coalition est encore réalisable.

    Vérifie notamment :

    - que les utilisateurs existent ;
    - qu'ils sont en ligne ;
    - qu'ils ne sont pas bloqués ;
    - que les ressources existent toujours ;
    - que les contraintes privées sont respectées.
    """

    reasons: list[str] = []

    user_by_id = {
        user.id: user
        for user in users
    }

    if len(set(proposal.participant_ids)) < 3:

        reasons.append(
            "not_enough_participants"
        )

    for participant_id in proposal.participant_ids:

        user = user_by_id.get(
            participant_id
        )

        if user is None:

            reasons.append(
                f"unknown_user:{participant_id}"
            )

            continue

        if not user.online:

            reasons.append(
                f"user_offline:{participant_id}"
            )

    # Quantité totale que chaque utilisateur
    # devrait céder par type de ressource.
    outgoing_quantities: dict[
        tuple[str, str, str],
        float
    ] = defaultdict(float)

    for transfer in proposal.transfers:

        provider = user_by_id.get(
            transfer.from_user_id
        )

        receiver = user_by_id.get(
            transfer.to_user_id
        )

        if provider is None or receiver is None:
            continue

        if (
            receiver.id
            in provider.blocked_partners
        ):
            reasons.append(
                "blocked_partner"
            )

        if (
            provider.id
            in receiver.blocked_partners
        ):
            reasons.append(
                "blocked_partner"
            )

        key = (
            provider.id,
            transfer.resource_type,
            transfer.unit
        )

        outgoing_quantities[key] += (
            transfer.quantity
        )

        matching_need = any(
            need.resource_type
            == transfer.resource_type

            and need.unit
            == transfer.unit

            and need.quantity
            <= transfer.quantity

            for need in receiver.needs
        )

        if not matching_need:

            reasons.append(
                f"receiver_does_not_need_resource:"
                f"{receiver.id}:"
                f"{transfer.resource_type}"
            )

    for (
        user_id,
        resource_type,
        unit
    ), required_quantity in outgoing_quantities.items():

        user = user_by_id[user_id]

        available_quantity = sum(

            resource.quantity

            for resource in user.resources

            if (
                resource.resource_type
                == resource_type

                and resource.unit
                == unit
            )
        )

        if available_quantity < required_quantity:

            reasons.append(
                f"insufficient_resource:"
                f"{user_id}:"
                f"{resource_type}"
            )

        private_limit = (
            user.constraints
            .max_quantity_to_give
            .get(resource_type)
        )

        if (
            private_limit is not None
            and required_quantity > private_limit
        ):

            reasons.append(
                f"private_constraint:"
                f"{user_id}:"
                f"{resource_type}"
            )

    return CoalitionFeasibility(
        feasible=len(reasons) == 0,
        reasons=reasons
    )


def find_possible_coalitions(
    users: list[User],
    target_user_id: str | None = None,
    min_size: int = 3,
    max_size: int = 4,
    max_results: int = 20
) -> list[CoalitionProposal]:
    """
    Fonction principale utilisée plus tard par CoalitionAgent.

    Elle :

    1. construit le graphe ;
    2. cherche les cycles ;
    3. construit des propositions ;
    4. élimine les coalitions impossibles.
    """

    cycles = find_exchange_cycles(
        users=users,

        min_size=min_size,
        max_size=max_size,

        target_user_id=target_user_id,

        max_results=max_results
    )

    proposals: list[
        CoalitionProposal
    ] = []

    for cycle in cycles:

        proposal = build_coalition_proposal(
            cycle,
            users
        )

        feasibility = (
            evaluate_coalition_feasibility(
                proposal,
                users
            )
        )

        if feasibility.feasible:

            proposals.append(
                proposal
            )

    return proposals