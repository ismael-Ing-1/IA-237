# app/agents/coalition_agent.py

from __future__ import annotations

from pydantic import BaseModel

from app.reputation import (
    ReputationManager,
)

from app.simulation import (
    SimulationWorld,
)

from app.tools.coalition_tools import (
    CoalitionProposal,
    find_possible_coalitions,
)


class RankedCoalition(BaseModel):
    """
    Coalition accompagnée de quelques informations
    permettant au PersonalAgent de choisir.
    """

    proposal: CoalitionProposal

    average_reputation: float

    participant_count: int

    score: float


class CoalitionAgent:
    """
    Agent spécialisé dans la découverte
    d'échanges multi-parties.

    Il ne peut PAS :

    - accepter une coalition ;
    - exécuter un échange ;
    - approuver au nom d'un utilisateur.

    Il retourne uniquement des possibilités.
    """

    def __init__(
        self,
        world: SimulationWorld,
        reputation: ReputationManager,
    ):
        self.world = world

        self.reputation = reputation

    # ========================================================
    # DISCOVERY
    # ========================================================

    def discover(
        self,
        target_user_id: str,
        min_size: int = 3,
        max_size: int = 4,
        max_results: int = 20,
    ) -> list[RankedCoalition]:
        """
        Trouve et classe les coalitions contenant
        target_user_id.
        """

        target_user = self.world.get_user(
            target_user_id
        )

        if target_user is None:

            raise ValueError(
                "Target user does not exist."
            )

        proposals = (
            find_possible_coalitions(
                users=self.world.get_users(),

                target_user_id=(
                    target_user_id
                ),

                min_size=min_size,

                max_size=max_size,

                max_results=max_results,
            )
        )

        ranked: list[
            RankedCoalition
        ] = []

        for proposal in proposals:

            reputation_scores = [
                self.reputation.get_score(
                    participant_id
                )

                for participant_id
                in proposal.participant_ids
            ]

            average_reputation = (
                sum(reputation_scores)
                / len(reputation_scores)
            )

            participant_count = len(
                proposal.participant_ids
            )

            # ----------------------------------------
            # SIMPLE MVP SCORE
            #
            # meilleure réputation = meilleur score
            # plus de participants = légère pénalité
            # ----------------------------------------

            complexity_penalty = (
                0.03
                * max(
                    0,
                    participant_count - 3,
                )
            )

            score = max(
                0.0,

                min(
                    1.0,

                    average_reputation
                    - complexity_penalty,
                ),
            )

            ranked.append(
                RankedCoalition(
                    proposal=proposal,

                    average_reputation=round(
                        average_reputation,
                        3,
                    ),

                    participant_count=(
                        participant_count
                    ),

                    score=round(
                        score,
                        3,
                    ),
                )
            )

        ranked.sort(
            key=lambda coalition: (
                -coalition.score,
                coalition.participant_count,
            )
        )

        return ranked

    def recommend(
        self,
        target_user_id: str,
        min_size: int = 3,
        max_size: int = 4,
    ) -> RankedCoalition | None:
        """
        Retourne la coalition jugée la plus prometteuse.

        Ce n'est PAS une acceptation automatique.
        """

        coalitions = self.discover(
            target_user_id=target_user_id,

            min_size=min_size,

            max_size=max_size,
        )

        if not coalitions:
            return None

        return coalitions[0]