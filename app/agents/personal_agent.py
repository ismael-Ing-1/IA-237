# app/agents/personal_agent.py

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.models import (
    Negotiation,
    Offer,
    PublicUserProfile,
    Resource,
    ResourceRequest,
)

from app.models.user import NegotiationStrategy

from app.agents.mediator_agent import (
    MediationEvaluation,
    MediationProposal,
)

from app.tools.coalition_tools import (
    CoalitionAgentEvaluation,
    CoalitionProposal,
)

from app.privacy import (
    PrivacyAction,
    PrivacyGuard,
)

from app.reputation import (
    ReputationManager,
)

from app.simulation import (
    SimulationWorld,
)

from app.tools.market_tools import (
    search_providers,
)

from app.tools.negotiation_tools import (
    accept_offer,
    counter_offer,
    create_negotiation,
    reject_offer,
    request_human_approval,
    send_offer,
)

from app.tools.privacy_tools import (
    can_user_give,
    is_partner_allowed,
)


# ============================================================
# STRUCTURED AGENT OUTPUTS
# ============================================================


class AgentAction(str, Enum):
    """
    Actions que le PersonalAgent peut décider d'effectuer.
    """

    SEARCH_MARKET = "search_market"

    START_NEGOTIATION = "start_negotiation"

    ACCEPT = "accept"

    COUNTER = "counter"

    REJECT = "reject"

    ASK_MEDIATOR = "ask_mediator"

    SEARCH_COALITION = "search_coalition"

    WAIT_HUMAN = "wait_human"

    STOP = "stop"


class CandidatePartner(BaseModel):
    """
    Information publique permettant au PersonalAgent
    de comparer plusieurs partenaires.
    """

    user_id: str

    display_name: str

    reputation: float

    preference_rank: int | None = None

    offered_resource_types: list[str] = Field(
        default_factory=list
    )

    requested_resource_types: list[str] = Field(
        default_factory=list
    )


class AgentDecision(BaseModel):
    """
    Décision structurée d'un agent.

    On évite de faire dépendre le programme
    d'une simple réponse textuelle du LLM.
    """

    action: AgentAction

    reason: str

    partner_id: str | None = None

    negotiation_id: str | None = None

    offer_id: str | None = None


class AgentStepResult(BaseModel):
    """
    Résultat d'une étape du PersonalAgent.
    """

    decision: AgentDecision

    negotiation: Negotiation | None = None

    offer: Offer | None = None


class NegotiationChoiceAction(str, Enum):
    ACCEPT = "accept"
    COUNTER = "counter"
    REJECT = "reject"
    ASK_MEDIATOR = "ask_mediator"


class InitialOfferOption(BaseModel):
    """
    One locally safe initial proposal.

    The quantity envelope comes from the human objective and private Python
    guards. The LLM may choose among these public proposals, but cannot invent
    an arbitrary amount outside this set.
    """

    choice_id: str
    label: str
    reason: str

    offered_resources: list[Resource] = Field(
        default_factory=list
    )
    requested_resources: list[ResourceRequest] = Field(
        default_factory=list
    )


class NegotiationResponseOption(BaseModel):
    """
    A response that Python has already determined is locally permissible.
    """

    choice_id: str
    action: NegotiationChoiceAction
    label: str
    reason: str

    offered_resources: list[Resource] = Field(
        default_factory=list
    )
    requested_resources: list[ResourceRequest] = Field(
        default_factory=list
    )


class NegotiationResponseSet(BaseModel):
    options: list[NegotiationResponseOption]
    fallback_choice_id: str


# ============================================================
# PERSONAL AGENT
# ============================================================


class PersonalAgent:
    """
    Agent représentant UN utilisateur.

    Il peut :

    - observer le marché ;
    - choisir un partenaire ;
    - commencer une négociation ;
    - recevoir une offre ;
    - accepter ;
    - rejeter ;
    - faire une contre-offre ;
    - demander une validation humaine.

    Il ne peut PAS :

    - modifier directement les ressources d'un autre user ;
    - contourner le PrivacyGuard ;
    - exécuter lui-même une transaction ;
    - accéder aux contraintes privées d'un autre utilisateur.
    """

    def __init__(
        self,
        user_id: str,
        world: SimulationWorld,
        reputation: ReputationManager,
        privacy_guard: PrivacyGuard,
    ):
        self.user_id = user_id

        self.world = world

        self.reputation = reputation

        self.privacy_guard = privacy_guard

        user = self.world.get_user(
            user_id
        )

        if user is None:
            raise ValueError(
                f"Utilisateur {user_id} introuvable."
            )

    # ========================================================
    # OWN USER
    # ========================================================

    @property
    def user(self):
        """
        Retourne uniquement l'utilisateur que
        cet agent est autorisé à représenter.
        """

        user = self.world.get_user(
            self.user_id
        )

        if user is None:
            raise RuntimeError(
                "L'utilisateur de cet agent "
                "n'existe plus dans le monde."
            )

        return user

    # ========================================================
    # MARKET OBSERVATION
    # ========================================================

    def discover_candidates(
        self,
        resource_type: str,
    ) -> list[CandidatePartner]:
        """
        Recherche les fournisseurs publics disponibles.

        L'agent ne reçoit que :

        - profil public ;
        - réputation ;
        - rang dans SES propres préférences.
        """

        profiles = search_providers(
            registry=self.world.registry,

            resource_type=resource_type,

            requester_id=self.user_id,

            blocked_ids=self.user.blocked_partners,
        )

        candidates: list[
            CandidatePartner
        ] = []

        for profile in profiles:

            score = self.reputation.get_score(
                profile.user_id
            )

            # Vérification déterministe.
            if not is_partner_allowed(
                self.user,
                profile.user_id,
                score,
            ):
                continue

            try:

                preference_rank = (
                    self.user
                    .preferred_partners
                    .index(
                        profile.user_id
                    )
                )

            except ValueError:

                preference_rank = None

            candidates.append(
                CandidatePartner(
                    user_id=profile.user_id,

                    display_name=(
                        profile.display_name
                    ),

                    reputation=score,

                    preference_rank=(
                        preference_rank
                    ),

                    offered_resource_types=(
                        profile
                        .offered_resource_types
                    ),

                    requested_resource_types=(
                        profile
                        .requested_resource_types
                    ),
                )
            )

        # ----------------------------------------
        # STRATEGY
        # ----------------------------------------
        #
        # FAST:
        #   priorité aux partenaires explicitement préférés,
        #   puis conserve l'ordre naturel du marché.
        #
        # CONSERVATIVE:
        #   priorité à la réputation, puis aux préférences.
        #
        # BALANCED / AGGRESSIVE:
        #   préférences puis réputation.
        #
        # AGGRESSIVE se différencie surtout dans handle_offer()
        # en tentant une amélioration des termes avant d'accepter.
        # ----------------------------------------

        strategy = self.user.strategy

        def preference_rank(
            candidate: CandidatePartner,
        ) -> int:
            return (
                candidate.preference_rank
                if candidate.preference_rank is not None
                else 10**9
            )

        if strategy == NegotiationStrategy.CONSERVATIVE:

            candidates.sort(
                key=lambda candidate: (
                    -candidate.reputation,
                    preference_rank(candidate),
                )
            )

        elif strategy == NegotiationStrategy.FAST:

            candidates.sort(
                key=lambda candidate: (
                    preference_rank(candidate),
                )
            )

        else:

            candidates.sort(
                key=lambda candidate: (
                    preference_rank(candidate),
                    -candidate.reputation,
                )
            )

        return candidates

    def choose_candidate(
        self,
        resource_type: str,
    ) -> CandidatePartner | None:
        """
        Sélectionne actuellement le premier candidat
        selon les préférences + réputation.

        Cette fonction sera plus tard un excellent
        endroit pour brancher un LLM.
        """

        candidates = (
            self.discover_candidates(
                resource_type
            )
        )

        if not candidates:
            return None

        return candidates[0]

    # ========================================================
    # GOAL
    # ========================================================

    def pursue_request(
        self,
        request: ResourceRequest,
        offered_resources: list[Resource],
        message: str | None = None,
    ) -> AgentStepResult:
        """
        Entrée principale simple du PersonalAgent.

        Exemple :

            request = 8 H100

        L'agent :

            recherche le marché
            ↓
            choisit un partenaire
            ↓
            crée une négociation
            ↓
            envoie une offre
        """

        candidate = self.choose_candidate(
            request.resource_type
        )

        if candidate is None:

            return AgentStepResult(
                decision=AgentDecision(
                    action=(
                        AgentAction.SEARCH_COALITION
                    ),

                    reason=(
                        "No acceptable direct provider "
                        "was found."
                    ),
                )
            )

        return self.start_negotiation(
            partner_id=candidate.user_id,

            offered_resources=(
                offered_resources
            ),

            requested_resources=[
                request
            ],

            message=message,
        )

    # ========================================================
    # START NEGOTIATION
    # ========================================================

    def start_negotiation(
        self,
        partner_id: str,
        offered_resources: list[Resource],
        requested_resources: list[ResourceRequest],
        message: str | None = None,
    ) -> AgentStepResult:
        """
        Commence une négociation avec un partenaire.

        Toutes les règles sont vérifiées AVANT
        l'envoi réel.
        """

        if partner_id == self.user_id:

            raise ValueError(
                "L'agent ne peut pas négocier "
                "avec lui-même."
            )

        public_profile = (
            self.world
            .registry
            .get_public_profile(
                partner_id
            )
        )

        if public_profile is None:

            raise ValueError(
                "Partenaire introuvable."
            )

        if not public_profile.online:

            raise ValueError(
                "Le partenaire est offline."
            )

        partner_reputation = (
            self.reputation.get_score(
                partner_id
            )
        )

        if not is_partner_allowed(
            self.user,
            partner_id,
            partner_reputation,
        ):

            raise ValueError(
                "Le partenaire n'est pas autorisé "
                "par les contraintes privées."
            )

        # Vérification déterministe de chaque ressource.
        for resource in offered_resources:

            if not can_user_give(
                self.user,
                resource.resource_type,
                resource.quantity,
            ):

                raise ValueError(
                    "Outgoing resource violates "
                    f"private constraints: "
                    f"{resource.resource_type}."
                )

        # ----------------------------------------
        # PREVIEW OFFER
        # ----------------------------------------

        preview = Offer(
            sender_id=self.user_id,

            receiver_id=partner_id,

            offered_resources=(
                offered_resources
            ),

            requested_resources=(
                requested_resources
            ),

            message=message,
        )

        privacy_result = (
            self.privacy_guard.check_offer(
                self.user,
                preview,
                partner_reputation=(
                    partner_reputation
                ),
            )
        )

        if (
            privacy_result.action
            == PrivacyAction.BLOCK
        ):

            raise ValueError(
                "PrivacyGuard blocked the offer."
            )

        safe_message = self._sanitize_message(
            message
        )

        # ----------------------------------------
        # CREATE NEGOTIATION
        # ----------------------------------------

        negotiation = create_negotiation(
            participant_ids=[
                self.user_id,
                partner_id,
            ],

            max_rounds=(
                self.user
                .constraints
                .max_negotiation_rounds
            ),
        )

        self.world.add_negotiation(
            negotiation
        )

        offer = send_offer(
            negotiation=negotiation,

            sender_id=self.user_id,

            receiver_id=partner_id,

            offered_resources=(
                offered_resources
            ),

            requested_resources=(
                requested_resources
            ),

            message=safe_message,
        )

        return AgentStepResult(
            decision=AgentDecision(
                action=(
                    AgentAction.START_NEGOTIATION
                ),

                reason=(
                    "Direct negotiation started."
                ),

                partner_id=partner_id,

                negotiation_id=(
                    negotiation.id
                ),

                offer_id=offer.id,
            ),

            negotiation=negotiation,

            offer=offer,
        )

    # ========================================================
    # RECEIVE OFFER
    # ========================================================

    def handle_offer(
        self,
        negotiation: Negotiation,
        offer: Offer,
    ) -> AgentStepResult:
        """Analyse une offre et négocie selon la stratégie de l'utilisateur.

        Les agents ne rejettent plus immédiatement une offre partielle si elle
        peut être réparée par une contre-offre sûre. Les contre-offres restent
        bornées par max_negotiation_rounds et par la politique de chaque agent.
        """

        if offer.receiver_id != self.user_id:
            raise ValueError(
                "Cette offre n'est pas adressée à cet agent."
            )

        partner_id = offer.sender_id
        partner_reputation = self.reputation.get_score(partner_id)

        if not is_partner_allowed(
            self.user,
            partner_id,
            partner_reputation,
        ):
            reject_offer(
                negotiation,
                offer.id,
                close_negotiation=True,
            )
            return AgentStepResult(
                decision=AgentDecision(
                    action=AgentAction.REJECT,
                    reason=(
                        "Partner violates trust or privacy constraints."
                    ),
                    partner_id=partner_id,
                    negotiation_id=negotiation.id,
                    offer_id=offer.id,
                ),
                negotiation=negotiation,
                offer=offer,
            )

        helpful = self._offer_has_matching_resource(offer)
        satisfies_need = self._offer_satisfies_need(offer)

        if not helpful:
            reject_offer(negotiation, offer.id)
            return AgentStepResult(
                decision=AgentDecision(
                    action=AgentAction.REJECT,
                    reason=(
                        "The offered resources do not match any current need."
                    ),
                    partner_id=partner_id,
                    negotiation_id=negotiation.id,
                    offer_id=offer.id,
                ),
                negotiation=negotiation,
                offer=offer,
            )

        privacy_result = self.privacy_guard.check_offer(
            self.user,
            offer,
            partner_reputation=partner_reputation,
        )

        # ----------------------------------------------------
        # REPAIR A PARTIAL OR UNSAFE OFFER
        # ----------------------------------------------------
        #
        # Une offre peut être pertinente sans satisfaire entièrement le besoin,
        # ou demander trop de ressources à cet utilisateur. Tant qu'un contre
        # raisonnable existe, on le propose au lieu de rejeter immédiatement.
        # ----------------------------------------------------

        if (
            not satisfies_need
            or privacy_result.action == PrivacyAction.BLOCK
        ):
            if negotiation.current_round >= negotiation.max_rounds:
                reject_offer(negotiation, offer.id)
                return AgentStepResult(
                    decision=AgentDecision(
                        action=AgentAction.REJECT,
                        reason=(
                            "Maximum negotiation rounds reached before safe terms could be found."
                        ),
                        partner_id=partner_id,
                        negotiation_id=negotiation.id,
                        offer_id=offer.id,
                    ),
                    negotiation=negotiation,
                    offer=offer,
                )

            counter_data = self._build_feasible_counter(offer)

            if counter_data is None:
                reject_offer(negotiation, offer.id)
                return AgentStepResult(
                    decision=AgentDecision(
                        action=AgentAction.REJECT,
                        reason=(
                            "No safe counter-offer can satisfy the current need and private constraints."
                        ),
                        partner_id=partner_id,
                        negotiation_id=negotiation.id,
                        offer_id=offer.id,
                    ),
                    negotiation=negotiation,
                    offer=offer,
                )

            resources_given, resources_requested = counter_data
            safe_message = self._sanitize_message(
                "Counter-offer adjusting the public terms to a safe feasible range."
            )
            new_offer = counter_offer(
                negotiation=negotiation,
                previous_offer_id=offer.id,
                sender_id=self.user_id,
                receiver_id=partner_id,
                offered_resources=resources_given,
                requested_resources=resources_requested,
                message=safe_message,
            )

            reason = (
                "The offer is relevant but does not yet fully satisfy the need, "
                "so the agent proposed safe terms that would."
                if not satisfies_need
                else
                "The incoming terms exceeded private constraints, so the agent "
                "proposed a safe counter-offer instead of rejecting immediately."
            )

            return AgentStepResult(
                decision=AgentDecision(
                    action=AgentAction.COUNTER,
                    reason=reason,
                    partner_id=partner_id,
                    negotiation_id=negotiation.id,
                    offer_id=new_offer.id,
                ),
                negotiation=negotiation,
                offer=new_offer,
            )

        # ----------------------------------------------------
        # STRATEGY-DRIVEN HAGGLING ON ALREADY SAFE TERMS
        # ----------------------------------------------------

        strategic_counter = self._build_strategy_counter(
            negotiation,
            offer,
        )

        if strategic_counter is not None:
            resources_given, resources_requested, reason = strategic_counter
            safe_message = self._sanitize_message(
                f"{self.user.strategy.value.capitalize()} strategy counter-offer."
            )
            new_offer = counter_offer(
                negotiation=negotiation,
                previous_offer_id=offer.id,
                sender_id=self.user_id,
                receiver_id=partner_id,
                offered_resources=resources_given,
                requested_resources=resources_requested,
                message=safe_message,
            )

            return AgentStepResult(
                decision=AgentDecision(
                    action=AgentAction.COUNTER,
                    reason=reason,
                    partner_id=partner_id,
                    negotiation_id=negotiation.id,
                    offer_id=new_offer.id,
                ),
                negotiation=negotiation,
                offer=new_offer,
            )

        accepted = accept_offer(negotiation, offer.id)
        strategy_label = self.user.strategy.value

        return AgentStepResult(
            decision=AgentDecision(
                action=AgentAction.ACCEPT,
                reason=(
                    "Offer satisfies the user's need and private constraints "
                    f"under the {strategy_label} strategy."
                ),
                partner_id=partner_id,
                negotiation_id=negotiation.id,
                offer_id=accepted.id,
            ),
            negotiation=negotiation,
            offer=accepted,
        )

    # ========================================================
    # COALITION PROPOSAL
    # ========================================================

    def evaluate_coalition_proposal(
        self,
        proposal: CoalitionProposal,
    ) -> CoalitionAgentEvaluation:
        """
        Privately validate this agent's part of a multi-party proposal.

        CoalitionAgent may coordinate a public cycle, but it never sees this
        agent's private limits. Only the resulting safe accept/reject verdict
        leaves the PersonalAgent.
        """

        if self.user_id not in proposal.participant_ids:
            return CoalitionAgentEvaluation(
                user_id=self.user_id,
                accepted=False,
                reason="Agent is not a participant in this coalition.",
            )

        if not self.user.online:
            return CoalitionAgentEvaluation(
                user_id=self.user_id,
                accepted=False,
                reason="Coalition rejected by the agent's current availability policy.",
            )

        incoming = [
            transfer
            for transfer in proposal.transfers
            if transfer.to_user_id == self.user_id
        ]
        outgoing = [
            transfer
            for transfer in proposal.transfers
            if transfer.from_user_id == self.user_id
        ]

        if not incoming or not outgoing:
            return CoalitionAgentEvaluation(
                user_id=self.user_id,
                accepted=False,
                reason="Coalition does not provide a complete exchange for this agent.",
            )

        counterpart_ids = {
            transfer.to_user_id
            for transfer in outgoing
        } | {
            transfer.from_user_id
            for transfer in incoming
        }

        for partner_id in counterpart_ids:
            partner = self.world.get_user(partner_id)
            if partner is None or not partner.online:
                return CoalitionAgentEvaluation(
                    user_id=self.user_id,
                    accepted=False,
                    reason="Coalition contains an unavailable counterparty.",
                )

            if not is_partner_allowed(
                self.user,
                partner_id,
                self.reputation.get_score(partner_id),
            ):
                return CoalitionAgentEvaluation(
                    user_id=self.user_id,
                    accepted=False,
                    reason="Coalition is not acceptable under this agent's private policy.",
                )

        outgoing_totals: dict[tuple[str, str], float] = {}
        for transfer in outgoing:
            key = (
                transfer.resource_type,
                transfer.unit,
            )
            outgoing_totals[key] = (
                outgoing_totals.get(key, 0.0)
                + transfer.quantity
            )

        for (
            resource_type,
            unit,
        ), quantity in outgoing_totals.items():
            if quantity <= 0:
                return CoalitionAgentEvaluation(
                    user_id=self.user_id,
                    accepted=False,
                    reason="Coalition contains invalid outgoing terms.",
                )

            available = sum(
                resource.quantity
                for resource in self.user.resources
                if (
                    resource.resource_type == resource_type
                    and resource.unit == unit
                )
            )

            private_limit = (
                self.user.constraints.max_quantity_to_give.get(
                    resource_type
                )
            )
            maximum = available
            if private_limit is not None:
                maximum = min(maximum, private_limit)

            if quantity > maximum:
                return CoalitionAgentEvaluation(
                    user_id=self.user_id,
                    accepted=False,
                    reason="Coalition is not acceptable under this agent's private policy.",
                )

            if (
                self.user.strategy == NegotiationStrategy.CONSERVATIVE
                and maximum > 0
                and quantity > maximum * 0.9
            ):
                return CoalitionAgentEvaluation(
                    user_id=self.user_id,
                    accepted=False,
                    reason="Coalition is not acceptable under this agent's private policy.",
                )

        incoming_totals: dict[tuple[str, str], float] = {}
        for transfer in incoming:
            key = (
                transfer.resource_type,
                transfer.unit,
            )
            incoming_totals[key] = (
                incoming_totals.get(key, 0.0)
                + transfer.quantity
            )

        satisfies_need = any(
            incoming_totals.get(
                (
                    need.resource_type,
                    need.unit,
                ),
                0.0,
            ) >= need.quantity
            for need in self.user.needs
        )

        if not satisfies_need:
            return CoalitionAgentEvaluation(
                user_id=self.user_id,
                accepted=False,
                reason="Coalition does not satisfy this agent's current objective.",
            )

        return CoalitionAgentEvaluation(
            user_id=self.user_id,
            accepted=True,
            reason="Coalition is acceptable under this agent's private policy.",
        )

    # ========================================================
    # MEDIATOR PROPOSAL
    # ========================================================

    def evaluate_mediation_proposal(
        self,
        proposal: MediationProposal,
    ) -> MediationEvaluation:
        """
        Privately evaluate a public mediator compromise.

        The mediator never sees the private reasons behind a rejection.
        This method does not mutate the live negotiation.
        """

        if self.user_id not in {
            proposal.sender_id,
            proposal.receiver_id,
        }:
            return MediationEvaluation(
                user_id=self.user_id,
                accepted=False,
                reason=(
                    "This agent is not a participant "
                    "in the mediator proposal."
                ),
            )

        if self.user_id == proposal.sender_id:
            partner_id = proposal.receiver_id
            outgoing = proposal.offered_resources
            incoming = proposal.requested_resources
        else:
            partner_id = proposal.sender_id
            outgoing = proposal.requested_resources
            incoming = proposal.offered_resources

        partner_reputation = self.reputation.get_score(
            partner_id
        )

        if not is_partner_allowed(
            self.user,
            partner_id,
            partner_reputation,
        ):
            return MediationEvaluation(
                user_id=self.user_id,
                accepted=False,
                reason=(
                    "Mediator compromise was rejected "
                    "by this agent's trust policy."
                ),
            )

        satisfies_need = any(
            item.resource_type == need.resource_type
            and item.unit == need.unit
            and item.quantity >= need.quantity
            for item in incoming
            for need in self.user.needs
        )

        if not satisfies_need:
            return MediationEvaluation(
                user_id=self.user_id,
                accepted=False,
                reason=(
                    "Mediator compromise does not satisfy "
                    "a current need."
                ),
            )

        for item in outgoing:
            if not can_user_give(
                self.user,
                item.resource_type,
                item.quantity,
            ):
                return MediationEvaluation(
                    user_id=self.user_id,
                    accepted=False,
                    reason=(
                        "Mediator compromise is outside "
                        "this agent's safe private range."
                    ),
                )

        preview = Offer(
            sender_id=proposal.sender_id,
            receiver_id=proposal.receiver_id,
            offered_resources=proposal.offered_resources,
            requested_resources=proposal.requested_resources,
            message="Public mediator compromise.",
        )

        privacy_result = self.privacy_guard.check_offer(
            self.user,
            preview,
            partner_reputation=partner_reputation,
        )

        if privacy_result.action == PrivacyAction.BLOCK:
            return MediationEvaluation(
                user_id=self.user_id,
                accepted=False,
                reason=(
                    "Mediator compromise is not compatible "
                    "with this agent's private policy."
                ),
            )

        return MediationEvaluation(
            user_id=self.user_id,
            accepted=True,
            reason=(
                "Mediator compromise satisfies this "
                "agent's need and private constraints."
            ),
        )


    # ========================================================
    # SAFE NEGOTIATION MENUS FOR THE LLM
    # ========================================================

    @staticmethod
    def _terms_signature(
        offered_resources: list[Resource],
        requested_resources: list[ResourceRequest],
    ) -> tuple:
        offered = tuple(
            sorted(
                (
                    item.resource_type,
                    item.unit,
                    round(item.quantity, 6),
                )
                for item in offered_resources
            )
        )
        requested = tuple(
            sorted(
                (
                    item.resource_type,
                    item.unit,
                    round(item.quantity, 6),
                )
                for item in requested_resources
            )
        )
        return offered, requested

    @staticmethod
    def _terms_text(
        offered_resources: list[Resource],
        requested_resources: list[ResourceRequest],
    ) -> str:
        gives = ", ".join(
            f"{item.quantity:g} {item.resource_type} {item.unit}"
            for item in offered_resources
        )
        wants = ", ".join(
            f"{item.quantity:g} {item.resource_type} {item.unit}"
            for item in requested_resources
        )
        return f"GIVE [{gives}] / REQUEST [{wants}]"

    def build_initial_offer_options(
        self,
        *,
        partner_id: str,
        authorized_offered_resources: list[Resource],
        requested_resources: list[ResourceRequest],
    ) -> list[InitialOfferOption]:
        """
        Build several different PUBLIC initial proposals.

        `authorized_offered_resources` is the envelope explicitly submitted by
        the human in GoalComposer. Private limits still remain local; every
        candidate is checked again through can_user_give + PrivacyGuard.

        In ACTIVE mode the LLM chooses one of these proposals.
        """

        partner = self.world.get_user(partner_id)
        if partner is None or not partner.online:
            return []

        partner_reputation = self.reputation.get_score(
            partner_id
        )

        if not is_partner_allowed(
            self.user,
            partner_id,
            partner_reputation,
        ):
            return []

        # give_factor, ask_factor
        profiles = [
            (
                "initial_direct",
                "Direct",
                1.00,
                1.00,
                "Offer the full human-authorized envelope and request exactly the objective.",
            ),
            (
                "initial_balanced",
                "Balanced opening",
                0.85,
                1.05,
                "Open with a moderate commitment while requesting a small improvement.",
            ),
            (
                "initial_cautious",
                "Cautious opening",
                0.70,
                1.00,
                "Commit less capacity while still requesting the full objective.",
            ),
            (
                "initial_assertive",
                "Assertive opening",
                0.75,
                1.12,
                "Ask for stronger public terms while keeping the outgoing commitment bounded.",
            ),
            (
                "initial_generous",
                "Generous opening",
                1.00,
                1.00,
                "Use the entire authorized envelope to maximize the chance of a quick deal.",
            ),
        ]

        options: list[InitialOfferOption] = []
        seen: set[tuple] = set()

        for (
            choice_id,
            label,
            give_factor,
            ask_factor,
            reason,
        ) in profiles:
            offered: list[Resource] = []

            valid = True
            for item in authorized_offered_resources:
                quantity = round(
                    item.quantity * give_factor,
                    3,
                )
                if (
                    quantity <= 0
                    or not can_user_give(
                        self.user,
                        item.resource_type,
                        quantity,
                    )
                ):
                    valid = False
                    break

                offered.append(
                    Resource(
                        resource_type=item.resource_type,
                        quantity=quantity,
                        unit=item.unit,
                        attributes=dict(item.attributes),
                    )
                )

            if not valid:
                continue

            requested = [
                ResourceRequest(
                    resource_type=item.resource_type,
                    quantity=round(
                        item.quantity * ask_factor,
                        3,
                    ),
                    unit=item.unit,
                    deadline=item.deadline,
                    attributes=dict(item.attributes),
                )
                for item in requested_resources
            ]

            preview = Offer(
                sender_id=self.user_id,
                receiver_id=partner_id,
                offered_resources=offered,
                requested_resources=requested,
            )

            privacy_result = self.privacy_guard.check_offer(
                self.user,
                preview,
                partner_reputation=partner_reputation,
            )

            if privacy_result.action == PrivacyAction.BLOCK:
                continue

            signature = self._terms_signature(
                offered,
                requested,
            )
            if signature in seen:
                continue

            seen.add(signature)
            options.append(
                InitialOfferOption(
                    choice_id=choice_id,
                    label=label,
                    reason=reason,
                    offered_resources=offered,
                    requested_resources=requested,
                )
            )

        return options

    def _is_offer_safely_acceptable(
        self,
        offer: Offer,
    ) -> bool:
        if offer.receiver_id != self.user_id:
            return False

        partner_id = offer.sender_id
        reputation = self.reputation.get_score(
            partner_id
        )

        if not is_partner_allowed(
            self.user,
            partner_id,
            reputation,
        ):
            return False

        if not self._offer_satisfies_need(offer):
            return False

        result = self.privacy_guard.check_offer(
            self.user,
            offer,
            partner_reputation=reputation,
        )

        return result.action != PrivacyAction.BLOCK

    def _build_llm_counter_option(
        self,
        *,
        incoming_offer: Offer,
        choice_id: str,
        label: str,
        give_factor: float,
        ask_factor: float,
        reason: str,
    ) -> NegotiationResponseOption | None:
        """
        Construct one locally-safe counter option.

        The partner's private limits are never read. The only private data used
        is this PersonalAgent's own local inventory/policy.
        """

        partner_id = incoming_offer.sender_id

        outgoing: list[Resource] = []
        for requested in incoming_offer.requested_resources:
            available = sum(
                resource.quantity
                for resource in self.user.resources
                if (
                    resource.resource_type
                    == requested.resource_type
                    and resource.unit
                    == requested.unit
                )
            )

            private_limit = (
                self.user.constraints
                .max_quantity_to_give
                .get(requested.resource_type)
            )

            maximum = available
            if private_limit is not None:
                maximum = min(
                    maximum,
                    private_limit,
                )

            quantity = min(
                requested.quantity * give_factor,
                maximum,
            )
            quantity = round(quantity, 3)

            if quantity <= 0:
                return None

            if not can_user_give(
                self.user,
                requested.resource_type,
                quantity,
            ):
                return None

            outgoing.append(
                Resource(
                    resource_type=requested.resource_type,
                    quantity=quantity,
                    unit=requested.unit,
                    attributes=dict(requested.attributes),
                )
            )

        requested_from_partner: list[
            ResourceRequest
        ] = []

        for offered in incoming_offer.offered_resources:
            matching_need = next(
                (
                    need
                    for need in self.user.needs
                    if (
                        need.resource_type
                        == offered.resource_type
                        and need.unit
                        == offered.unit
                    )
                ),
                None,
            )

            if matching_need is None:
                continue

            quantity = round(
                max(
                    matching_need.quantity,
                    offered.quantity * ask_factor,
                ),
                3,
            )

            requested_from_partner.append(
                ResourceRequest(
                    resource_type=offered.resource_type,
                    quantity=quantity,
                    unit=offered.unit,
                    deadline=matching_need.deadline,
                    attributes=dict(
                        matching_need.attributes
                    ),
                )
            )

        if not outgoing or not requested_from_partner:
            return None

        # Avoid a useless "counter" that simply mirrors the currently offered
        # agreement. ACCEPT is the correct action in that case.
        reciprocal_signature = self._terms_signature(
            [
                Resource(
                    resource_type=item.resource_type,
                    quantity=item.quantity,
                    unit=item.unit,
                    attributes=dict(item.attributes),
                )
                for item in incoming_offer.requested_resources
            ],
            [
                ResourceRequest(
                    resource_type=item.resource_type,
                    quantity=item.quantity,
                    unit=item.unit,
                    attributes=dict(item.attributes),
                )
                for item in incoming_offer.offered_resources
            ],
        )

        if (
            self._terms_signature(
                outgoing,
                requested_from_partner,
            )
            == reciprocal_signature
        ):
            return None

        preview = Offer(
            sender_id=self.user_id,
            receiver_id=partner_id,
            offered_resources=outgoing,
            requested_resources=requested_from_partner,
        )

        privacy_result = self.privacy_guard.check_offer(
            self.user,
            preview,
            partner_reputation=(
                self.reputation.get_score(
                    partner_id
                )
            ),
        )

        if privacy_result.action == PrivacyAction.BLOCK:
            return None

        return NegotiationResponseOption(
            choice_id=choice_id,
            action=NegotiationChoiceAction.COUNTER,
            label=label,
            reason=reason,
            offered_resources=outgoing,
            requested_resources=(
                requested_from_partner
            ),
        )

    def build_response_options(
        self,
        negotiation: Negotiation,
        offer: Offer,
    ) -> NegotiationResponseSet:
        """
        Build the complete action menu for one negotiation turn.

        This is the key boundary for full LLM negotiation:
        the model chooses WHAT happens, while Python guarantees that every
        offered counter is executable under this agent's own local policy.
        """

        if offer.receiver_id != self.user_id:
            raise ValueError(
                "Offer is not addressed to this agent."
            )

        # Determine the deterministic fallback without mutating live state.
        preview_negotiation = negotiation.model_copy(
            deep=True
        )
        preview_offer = preview_negotiation.get_offer(
            offer.id
        )
        if preview_offer is None:
            raise ValueError(
                "Offer disappeared during local-policy preview."
            )

        preview_result = self.handle_offer(
            preview_negotiation,
            preview_offer,
        )

        options: list[
            NegotiationResponseOption
        ] = []

        # Deterministic fallback becomes an explicit option.
        if (
            preview_result.decision.action
            == AgentAction.ACCEPT
        ):
            fallback_choice_id = "accept"
            options.append(
                NegotiationResponseOption(
                    choice_id="accept",
                    action=(
                        NegotiationChoiceAction
                        .ACCEPT
                    ),
                    label="Accept",
                    reason=(
                        "Accept the current safe public terms."
                    ),
                )
            )

        elif (
            preview_result.decision.action
            == AgentAction.COUNTER
            and preview_result.offer is not None
        ):
            fallback_choice_id = "counter_local"
            options.append(
                NegotiationResponseOption(
                    choice_id="counter_local",
                    action=(
                        NegotiationChoiceAction
                        .COUNTER
                    ),
                    label="Local policy counter",
                    reason=(
                        preview_result.decision.reason
                    ),
                    offered_resources=[
                        item.model_copy(deep=True)
                        for item
                        in preview_result.offer
                        .offered_resources
                    ],
                    requested_resources=[
                        item.model_copy(deep=True)
                        for item
                        in preview_result.offer
                        .requested_resources
                    ],
                )
            )

        else:
            fallback_choice_id = "reject"
            options.append(
                NegotiationResponseOption(
                    choice_id="reject",
                    action=(
                        NegotiationChoiceAction
                        .REJECT
                    ),
                    label="Reject",
                    reason=(
                        preview_result.decision.reason
                    ),
                )
            )

        # ACCEPT is always offered when it is truly safe, even if the
        # deterministic strategy would haggle first.
        if (
            self._is_offer_safely_acceptable(
                offer
            )
            and not any(
                item.choice_id == "accept"
                for item in options
            )
        ):
            options.append(
                NegotiationResponseOption(
                    choice_id="accept",
                    action=(
                        NegotiationChoiceAction
                        .ACCEPT
                    ),
                    label="Accept current terms",
                    reason=(
                        "Current public terms already "
                        "satisfy the need and local policy."
                    ),
                )
            )

        if (
            negotiation.current_round
            < negotiation.max_rounds
        ):
            counter_profiles = [
                (
                    "counter_cautious",
                    "Cautious counter",
                    0.72,
                    1.10,
                    "Preserve more outgoing capacity and ask for stronger terms.",
                ),
                (
                    "counter_firm",
                    "Firm counter",
                    0.84,
                    1.07,
                    "Make a meaningful concession while still improving the public exchange.",
                ),
                (
                    "counter_balanced",
                    "Balanced counter",
                    0.94,
                    1.03,
                    "Move closer to agreement with a modest improvement request.",
                ),
                (
                    "counter_bridge",
                    "Bridge counter",
                    1.00,
                    1.00,
                    "Move as close as possible to the current public terms while still satisfying the need.",
                ),
            ]

            existing_signatures = {
                self._terms_signature(
                    item.offered_resources,
                    item.requested_resources,
                )
                for item in options
                if (
                    item.action
                    == NegotiationChoiceAction.COUNTER
                )
            }

            for (
                choice_id,
                label,
                give_factor,
                ask_factor,
                reason,
            ) in counter_profiles:
                option = (
                    self._build_llm_counter_option(
                        incoming_offer=offer,
                        choice_id=choice_id,
                        label=label,
                        give_factor=give_factor,
                        ask_factor=ask_factor,
                        reason=reason,
                    )
                )

                if option is None:
                    continue

                signature = self._terms_signature(
                    option.offered_resources,
                    option.requested_resources,
                )
                if signature in existing_signatures:
                    continue

                existing_signatures.add(
                    signature
                )
                options.append(option)

        if not any(
            item.choice_id == "reject"
            for item in options
        ):
            options.append(
                NegotiationResponseOption(
                    choice_id="reject",
                    action=(
                        NegotiationChoiceAction
                        .REJECT
                    ),
                    label="Reject and try another path",
                    reason=(
                        "End this bilateral attempt "
                        "without accepting unsafe or "
                        "unattractive terms."
                    ),
                )
            )

        if len(negotiation.offers) >= 2:
            options.append(
                NegotiationResponseOption(
                    choice_id="ask_mediator",
                    action=(
                        NegotiationChoiceAction
                        .ASK_MEDIATOR
                    ),
                    label="Ask mediator",
                    reason=(
                        "Request a public-only mediator "
                        "before abandoning the bilateral path."
                    ),
                )
            )

        return NegotiationResponseSet(
            options=options,
            fallback_choice_id=(
                fallback_choice_id
            ),
        )

    def apply_response_option(
        self,
        negotiation: Negotiation,
        offer: Offer,
        option: NegotiationResponseOption,
    ) -> AgentStepResult:
        """
        Execute an already-generated safe choice on live state.

        The LLM never calls negotiation tools directly.
        """

        partner_id = offer.sender_id

        if (
            option.action
            == NegotiationChoiceAction.ACCEPT
        ):
            if not self._is_offer_safely_acceptable(
                offer
            ):
                raise ValueError(
                    "Selected accept option is no longer safe."
                )

            accepted = accept_offer(
                negotiation,
                offer.id,
            )

            return AgentStepResult(
                decision=AgentDecision(
                    action=AgentAction.ACCEPT,
                    reason=option.reason,
                    partner_id=partner_id,
                    negotiation_id=negotiation.id,
                    offer_id=accepted.id,
                ),
                negotiation=negotiation,
                offer=accepted,
            )

        if (
            option.action
            == NegotiationChoiceAction.COUNTER
        ):
            if not option.offered_resources:
                raise ValueError(
                    "Counter option has no outgoing terms."
                )

            for resource in option.offered_resources:
                if not can_user_give(
                    self.user,
                    resource.resource_type,
                    resource.quantity,
                ):
                    raise ValueError(
                        "Counter option is no longer safe."
                    )

            preview = Offer(
                sender_id=self.user_id,
                receiver_id=partner_id,
                offered_resources=(
                    option.offered_resources
                ),
                requested_resources=(
                    option.requested_resources
                ),
            )

            privacy_result = (
                self.privacy_guard.check_offer(
                    self.user,
                    preview,
                    partner_reputation=(
                        self.reputation.get_score(
                            partner_id
                        )
                    ),
                )
            )

            if (
                privacy_result.action
                == PrivacyAction.BLOCK
            ):
                raise ValueError(
                    "Counter option was blocked by local policy."
                )

            new_offer = counter_offer(
                negotiation=negotiation,
                previous_offer_id=offer.id,
                sender_id=self.user_id,
                receiver_id=partner_id,
                offered_resources=[
                    item.model_copy(deep=True)
                    for item
                    in option.offered_resources
                ],
                requested_resources=[
                    item.model_copy(deep=True)
                    for item
                    in option.requested_resources
                ],
                message=self._sanitize_message(
                    "LLM-selected counter-offer from locally safe terms."
                ),
            )

            return AgentStepResult(
                decision=AgentDecision(
                    action=AgentAction.COUNTER,
                    reason=option.reason,
                    partner_id=partner_id,
                    negotiation_id=negotiation.id,
                    offer_id=new_offer.id,
                ),
                negotiation=negotiation,
                offer=new_offer,
            )

        if (
            option.action
            == NegotiationChoiceAction.ASK_MEDIATOR
        ):
            return AgentStepResult(
                decision=AgentDecision(
                    action=AgentAction.ASK_MEDIATOR,
                    reason=option.reason,
                    partner_id=partner_id,
                    negotiation_id=negotiation.id,
                    offer_id=offer.id,
                ),
                negotiation=negotiation,
                offer=offer,
            )

        rejected = reject_offer(
            negotiation,
            offer.id,
        )

        return AgentStepResult(
            decision=AgentDecision(
                action=AgentAction.REJECT,
                reason=option.reason,
                partner_id=partner_id,
                negotiation_id=negotiation.id,
                offer_id=offer.id,
            ),
            negotiation=negotiation,
            offer=rejected,
        )

    # ========================================================
    # HUMAN APPROVAL
    # ========================================================

    def request_human_validation(
        self,
        negotiation: Negotiation,
    ) -> AgentDecision:
        """
        L'agent ne peut pas exécuter l'échange.

        Il passe simplement à WAITING_HUMAN.
        """

        request_human_approval(
            negotiation
        )

        return AgentDecision(
            action=AgentAction.WAIT_HUMAN,

            reason=(
                "An agreement was found and requires "
                "human approval before execution."
            ),

            negotiation_id=(
                negotiation.id
            ),
        )

    # ========================================================
    # PRIVATE HELPERS
    # ========================================================

    def _offer_has_matching_resource(
        self,
        offer: Offer,
    ) -> bool:
        """True si l'offre apporte au moins une ressource utile, même partiellement."""

        return any(
            offered.resource_type == need.resource_type
            and offered.unit == need.unit
            and offered.quantity > 0
            for offered in offer.offered_resources
            for need in self.user.needs
        )

    def _offer_satisfies_need(
        self,
        offer: Offer,
    ) -> bool:
        """
        Vérifie si ce que l'autre utilisateur propose
        satisfait au moins un besoin de cet utilisateur.
        """

        for offered in offer.offered_resources:

            for need in self.user.needs:

                if (
                    offered.resource_type
                    == need.resource_type

                    and offered.unit
                    == need.unit

                    and offered.quantity
                    >= need.quantity
                ):

                    return True

        return False

    def _build_strategy_counter(
        self,
        negotiation: Negotiation,
        incoming_offer: Offer,
    ) -> tuple[
        list[Resource],
        list[ResourceRequest],
        str,
    ] | None:
        """Construit une contre-offre selon la politique de négociation.

        FAST
            accepte les termes sûrs immédiatement.

        BALANCED
            tente une amélioration modeste une seule fois.

        CONSERVATIVE
            protège davantage sa capacité : deux concessions graduelles
            avant d'accepter des termes sûrs.

        AGGRESSIVE
            peut demander des termes plus favorables jusqu'à trois fois,
            avec une exigence décroissante pour favoriser la convergence.

        Chaque proposition repasse par PrivacyGuard. Aucune limite privée du
        partenaire n'est lue ici : le partenaire évaluera la contre-offre lui-même.
        """

        if negotiation.current_round >= negotiation.max_rounds:
            return None

        strategy = self.user.strategy
        counter_count = sum(
            1
            for item in negotiation.offers
            if item.sender_id == self.user_id
            and item.parent_offer_id is not None
        )

        # (give_factor, ask_factor, reason)
        schedules: dict[NegotiationStrategy, list[tuple[float, float, str]]] = {
            NegotiationStrategy.FAST: [],
            NegotiationStrategy.BALANCED: [
                (
                    1.0,
                    1.05,
                    "Balanced strategy: one modest counter-offer seeks slightly better terms before accepting.",
                ),
            ],
            NegotiationStrategy.CONSERVATIVE: [
                (
                    0.90,
                    1.0,
                    "Conservative strategy: the agent initially preserves more of its capacity.",
                ),
                (
                    0.95,
                    1.0,
                    "Conservative strategy: the agent makes a gradual concession while staying inside private limits.",
                ),
            ],
            NegotiationStrategy.AGGRESSIVE: [
                (
                    1.0,
                    1.15,
                    "Aggressive strategy: the agent asks for stronger terms while the negotiation still has room.",
                ),
                (
                    1.0,
                    1.10,
                    "Aggressive strategy: the agent softens its demand but continues negotiating for a better deal.",
                ),
                (
                    1.0,
                    1.05,
                    "Aggressive strategy: final modest improvement attempt before accepting safe terms.",
                ),
            ],
        }

        schedule = schedules[strategy]
        if counter_count >= len(schedule):
            return None

        give_factor, ask_factor, reason = schedule[counter_count]

        resources_given: list[Resource] = []
        for requested in incoming_offer.requested_resources:
            quantity = round(requested.quantity * give_factor, 3)
            if quantity <= 0 or not can_user_give(
                self.user,
                requested.resource_type,
                quantity,
            ):
                return None

            resources_given.append(
                Resource(
                    resource_type=requested.resource_type,
                    quantity=quantity,
                    unit=requested.unit,
                    attributes=dict(requested.attributes),
                )
            )

        resources_requested: list[ResourceRequest] = []
        for offered in incoming_offer.offered_resources:
            matching_need = next(
                (
                    need
                    for need in self.user.needs
                    if need.resource_type == offered.resource_type
                    and need.unit == offered.unit
                ),
                None,
            )
            if matching_need is None:
                continue

            quantity = round(
                max(
                    matching_need.quantity,
                    offered.quantity * ask_factor,
                ),
                3,
            )
            resources_requested.append(
                ResourceRequest(
                    resource_type=offered.resource_type,
                    quantity=quantity,
                    unit=offered.unit,
                    deadline=matching_need.deadline,
                    attributes=dict(matching_need.attributes),
                )
            )

        if not resources_given or not resources_requested:
            return None

        preview = Offer(
            sender_id=self.user_id,
            receiver_id=incoming_offer.sender_id,
            offered_resources=resources_given,
            requested_resources=resources_requested,
        )

        result = self.privacy_guard.check_offer(
            self.user,
            preview,
            partner_reputation=self.reputation.get_score(
                incoming_offer.sender_id
            ),
        )
        if result.action == PrivacyAction.BLOCK:
            return None

        return resources_given, resources_requested, reason

    def _build_feasible_counter(
        self,
        incoming_offer: Offer,
    ) -> tuple[
        list[Resource],
        list[ResourceRequest],
    ] | None:
        """
        Génère une contre-offre sans exposer
        les limites privées.

        Exemple :

        Alice demande 8 H100 à Bob.

        Bob ne peut céder que 5.

        Bob contre-propose :

            5 H100
            contre
            le STORAGE d'Alice.
        """

        resources_given: list[
            Resource
        ] = []

        # Ce que l'autre agent nous demande.
        for requested in (
            incoming_offer
            .requested_resources
        ):

            available = (
                self.user
                .get_resource_quantity(
                    requested.resource_type
                )
            )

            private_limit = (
                self.user
                .constraints
                .max_quantity_to_give
                .get(
                    requested.resource_type
                )
            )

            maximum = available

            if private_limit is not None:

                maximum = min(
                    maximum,
                    private_limit,
                )

            quantity = min(
                requested.quantity,
                maximum,
            )

            if quantity <= 0:
                return None

            resources_given.append(
                Resource(
                    resource_type=(
                        requested.resource_type
                    ),

                    quantity=quantity,

                    unit=requested.unit,

                    attributes=dict(
                        requested.attributes
                    ),
                )
            )

        resources_requested: list[
            ResourceRequest
        ] = []

        # Ce que l'autre agent nous propose.
        for offered in (
            incoming_offer
            .offered_resources
        ):

            matching_need = next(
                (
                    need

                    for need
                    in self.user.needs

                    if (
                        need.resource_type
                        == offered.resource_type

                        and need.unit
                        == offered.unit
                    )
                ),
                None,
            )

            if matching_need is None:
                continue

            requested_quantity = max(
                offered.quantity,
                matching_need.quantity,
            )

            resources_requested.append(
                ResourceRequest(
                    resource_type=(
                        offered.resource_type
                    ),

                    quantity=(
                        requested_quantity
                    ),

                    unit=offered.unit,

                    deadline=(
                        matching_need.deadline
                    ),

                    attributes=dict(
                        matching_need.attributes
                    ),
                )
            )

        if (
            not resources_given
            or not resources_requested
        ):
            return None

        # ----------------------------------------
        # VERIFY THE GENERATED COUNTER
        # ----------------------------------------

        preview = Offer(
            sender_id=self.user_id,

            receiver_id=(
                incoming_offer.sender_id
            ),

            offered_resources=(
                resources_given
            ),

            requested_resources=(
                resources_requested
            ),
        )

        result = self.privacy_guard.check_offer(
            self.user,

            preview,

            partner_reputation=(
                self.reputation.get_score(
                    incoming_offer.sender_id
                )
            ),
        )

        if (
            result.action
            == PrivacyAction.BLOCK
        ):
            return None

        return (
            resources_given,
            resources_requested,
        )

    def _sanitize_message(
        self,
        message: str | None,
    ) -> str | None:
        """
        Tous les messages sortants passent
        obligatoirement par le PrivacyGuard.
        """

        if message is None:
            return None

        result = (
            self.privacy_guard
            .check_message(
                self.user,
                message,
            )
        )

        if (
            result.action
            == PrivacyAction.BLOCK
        ):

            raise ValueError(
                "PrivacyGuard blocked outgoing message."
            )

        return result.sanitized_message