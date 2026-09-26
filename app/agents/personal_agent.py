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
                )
            )

        # ----------------------------------------
        # STRATEGY
        #
        # 1. preferred partners
        # 2. reputation
        # ----------------------------------------

        candidates.sort(
            key=lambda candidate: (
                (
                    candidate.preference_rank
                    if candidate.preference_rank
                    is not None
                    else 10**9
                ),
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
        """
        Analyse une offre reçue.

        Politique MVP :

        1. partenaire autorisé ?
        2. offre répond à un besoin ?
        3. contraintes privées respectées ?
        4. oui -> ACCEPT
        5. sinon essayer COUNTER
        6. sinon REJECT
        """

        if offer.receiver_id != self.user_id:

            raise ValueError(
                "Cette offre n'est pas adressée "
                "à cet agent."
            )

        partner_id = offer.sender_id

        partner_reputation = (
            self.reputation.get_score(
                partner_id
            )
        )

        # ----------------------------------------
        # PARTNER VALIDATION
        # ----------------------------------------

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
                        "Partner violates trust "
                        "or privacy constraints."
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

        # ----------------------------------------
        # DOES THE OFFER HELP?
        # ----------------------------------------

        if not self._offer_satisfies_need(
            offer
        ):

            reject_offer(
                negotiation,
                offer.id,
            )

            return AgentStepResult(
                decision=AgentDecision(
                    action=AgentAction.REJECT,

                    reason=(
                        "The offered resources do not "
                        "satisfy a current need."
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

        # ----------------------------------------
        # PRIVATE CONSTRAINTS
        # ----------------------------------------

        privacy_result = (
            self.privacy_guard.check_offer(
                self.user,
                offer,
                partner_reputation=(
                    partner_reputation
                ),
            )
        )

        if (
            privacy_result.action
            != PrivacyAction.BLOCK
        ):

            accepted = accept_offer(
                negotiation,
                offer.id,
            )

            return AgentStepResult(
                decision=AgentDecision(
                    action=AgentAction.ACCEPT,

                    reason=(
                        "Offer satisfies the user's "
                        "need and private constraints."
                    ),

                    partner_id=partner_id,

                    negotiation_id=(
                        negotiation.id
                    ),

                    offer_id=accepted.id,
                ),

                negotiation=negotiation,

                offer=accepted,
            )

        # ----------------------------------------
        # TRY COUNTER OFFER
        # ----------------------------------------

        counter_data = (
            self._build_feasible_counter(
                offer
            )
        )

        if counter_data is None:

            reject_offer(
                negotiation,
                offer.id,
            )

            return AgentStepResult(
                decision=AgentDecision(
                    action=AgentAction.REJECT,

                    reason=(
                        "No safe counter-offer "
                        "can be generated."
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

        (
            resources_given,
            resources_requested,
        ) = counter_data

        safe_message = self._sanitize_message(
            "Counter-offer based on my current constraints."
        )

        new_offer = counter_offer(
            negotiation=negotiation,

            previous_offer_id=offer.id,

            sender_id=self.user_id,

            receiver_id=partner_id,

            offered_resources=(
                resources_given
            ),

            requested_resources=(
                resources_requested
            ),

            message=safe_message,
        )

        return AgentStepResult(
            decision=AgentDecision(
                action=AgentAction.COUNTER,

                reason=(
                    "The original offer exceeded "
                    "private constraints, so a safe "
                    "counter-offer was generated."
                ),

                partner_id=partner_id,

                negotiation_id=(
                    negotiation.id
                ),

                offer_id=new_offer.id,
            ),

            negotiation=negotiation,

            offer=new_offer,
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