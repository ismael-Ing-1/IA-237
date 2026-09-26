# app/simulation/world.py

from __future__ import annotations

import heapq

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from itertools import count

from app.market.registry import MarketRegistry
from app.market.exchange import execute_exchange

from app.models.user import User
from app.models.resource import Resource
from app.models.negotiation import (
    Negotiation,
    NegotiationStatus,
)

from app.simulation.events import (
    EventExecution,
    EventType,
    MarketEvent,
)


class SimulationWorld:
    """
    Monde simulé contenant :

    - les utilisateurs ;
    - le marketplace ;
    - les négociations ;
    - les événements ;
    - le temps virtuel.

    Le temps N'AVANCE JAMAIS automatiquement.

    Il évolue uniquement lorsqu'on appelle :

        world.advance_time(...)
    """

    def __init__(
        self,
        start_time: datetime | None = None,
        registry: MarketRegistry | None = None,
    ):
        # ----------------------------------------
        # TEMPS VIRTUEL
        # ----------------------------------------

        if start_time is None:

            start_time = datetime.now(
                timezone.utc
            )

        if (
            start_time.tzinfo is None
            or start_time.utcoffset() is None
        ):
            raise ValueError(
                "start_time doit contenir un timezone."
            )

        self.current_time = start_time

        # ----------------------------------------
        # UTILISATEURS
        # ----------------------------------------

        self.users: dict[str, User] = {}

        # ----------------------------------------
        # MARKET
        # ----------------------------------------

        self.registry = (
            registry
            if registry is not None
            else MarketRegistry()
        )

        # ----------------------------------------
        # NEGOTIATIONS
        # ----------------------------------------

        self.active_negotiations: dict[
            str,
            Negotiation
        ] = {}

        self.completed_negotiations: dict[
            str,
            Negotiation
        ] = {}

        # ----------------------------------------
        # EVENTS
        # ----------------------------------------

        # Priority queue :
        #
        # (
        #   scheduled_timestamp,
        #   sequence_number,
        #   MarketEvent
        # )
        #
        # sequence_number garantit l'ordre
        # si deux événements ont exactement
        # la même date.

        self._event_queue: list[
            tuple[
                float,
                int,
                MarketEvent,
            ]
        ] = []

        self._event_counter = count()

        self.event_history: list[
            EventExecution
        ] = []

    # ========================================================
    # USERS
    # ========================================================

    def add_user(
        self,
        user: User,
    ) -> None:
        """
        Ajoute un utilisateur au monde
        et l'enregistre dans le marketplace.
        """

        if user.id in self.users:
            raise ValueError(
                f"L'utilisateur {user.id} existe déjà."
            )

        self.users[user.id] = user

        self.registry.register_user(
            user
        )

    def get_user(
        self,
        user_id: str,
    ) -> User | None:
        """
        Retourne un utilisateur par son ID.
        """

        return self.users.get(
            user_id
        )

    def get_users(
        self,
    ) -> list[User]:
        """
        Retourne tous les utilisateurs.
        """

        return list(
            self.users.values()
        )

    # ========================================================
    # NEGOTIATIONS
    # ========================================================

    def add_negotiation(
        self,
        negotiation: Negotiation,
    ) -> None:
        """
        Ajoute une négociation active.
        """

        if negotiation.id in self.active_negotiations:

            raise ValueError(
                "Cette négociation existe déjà."
            )

        self.active_negotiations[
            negotiation.id
        ] = negotiation

    def get_negotiation(
        self,
        negotiation_id: str,
    ) -> Negotiation | None:

        negotiation = (
            self.active_negotiations.get(
                negotiation_id
            )
        )

        if negotiation is not None:
            return negotiation

        return (
            self.completed_negotiations.get(
                negotiation_id
            )
        )

    def get_active_negotiations(
        self,
    ) -> list[Negotiation]:

        return list(
            self.active_negotiations.values()
        )

    def execute_negotiation(
        self,
        negotiation_id: str,
    ) -> bool:
        """
        Exécute un échange après validation humaine.

        La négociation doit être dans l'état APPROVED.
        """

        negotiation = (
            self.active_negotiations.get(
                negotiation_id
            )
        )

        if negotiation is None:

            raise ValueError(
                f"Négociation {negotiation_id} introuvable."
            )

        if (
            negotiation.status
            != NegotiationStatus.APPROVED
        ):

            raise ValueError(
                "La négociation doit être APPROVED "
                "avant l'exécution."
            )

        success = execute_exchange(
            negotiation,
            self.users,
        )

        if success:

            self.completed_negotiations[
                negotiation.id
            ] = negotiation

            del self.active_negotiations[
                negotiation.id
            ]

        return success

    # ========================================================
    # EVENTS
    # ========================================================

    def schedule_event(
        self,
        event: MarketEvent,
    ) -> None:
        """
        Programme un événement futur.

        Exemple :

            world.schedule_event(
                MarketEvent(...)
            )
        """

        if (
            event.scheduled_at
            < self.current_time
        ):
            raise ValueError(
                "Impossible de programmer "
                "un événement dans le passé."
            )

        heapq.heappush(
            self._event_queue,
            (
                event.scheduled_at.timestamp(),
                next(self._event_counter),
                event,
            ),
        )

    def schedule_event_in(
        self,
        delay: timedelta,
        event_type: EventType,
        user_id: str,
        **kwargs,
    ) -> MarketEvent:
        """
        Fonction pratique permettant de programmer :

            "dans 10 minutes"

        plutôt que de calculer soi-même la date.
        """

        if delay.total_seconds() < 0:
            raise ValueError(
                "delay ne peut pas être négatif."
            )

        event = MarketEvent(
            event_type=event_type,
            user_id=user_id,

            scheduled_at=(
                self.current_time
                + delay
            ),

            **kwargs,
        )

        self.schedule_event(
            event
        )

        return event

    def get_scheduled_events(
        self,
    ) -> list[MarketEvent]:
        """
        Retourne les événements futurs
        triés chronologiquement.
        """

        events = sorted(
            self._event_queue,
            key=lambda item: (
                item[0],
                item[1],
            ),
        )

        return [
            item[2]
            for item in events
        ]

    # ========================================================
    # VIRTUAL TIME
    # ========================================================

    def advance_time(
        self,
        *,
        seconds: float = 0,
        minutes: float = 0,
        hours: float = 0,
        days: float = 0,
    ) -> list[EventExecution]:
        """
        Fait avancer le temps VIRTUEL.

        Exemple :

            world.advance_time(minutes=10)

        Il n'y a AUCUN sleep().

        Tous les événements programmés entre :

            ancien current_time

        et :

            nouveau current_time

        sont exécutés dans l'ordre.
        """

        delta = timedelta(
            seconds=seconds,
            minutes=minutes,
            hours=hours,
            days=days,
        )

        if delta.total_seconds() < 0:

            raise ValueError(
                "Le temps ne peut pas reculer."
            )

        target_time = (
            self.current_time
            + delta
        )

        return self.run_until(
            target_time
        )

    def run_until(
        self,
        target_time: datetime,
    ) -> list[EventExecution]:
        """
        Fait avancer directement la simulation
        jusqu'à target_time.
        """

        if (
            target_time.tzinfo is None
            or target_time.utcoffset() is None
        ):
            raise ValueError(
                "target_time doit contenir un timezone."
            )

        if target_time < self.current_time:

            raise ValueError(
                "Le temps virtuel ne peut pas reculer."
            )

        executions: list[
            EventExecution
        ] = []

        # Tant qu'un événement doit arriver
        # avant target_time...
        while self._event_queue:

            (
                timestamp,
                _,
                event,
            ) = self._event_queue[0]

            event_time = datetime.fromtimestamp(
                timestamp,
                tz=timezone.utc,
            )

            if event_time > target_time:
                break

            # Retirer l'événement de la queue.
            heapq.heappop(
                self._event_queue
            )

            # Le temps virtuel avance EXACTEMENT
            # jusqu'au moment de l'événement.
            self.current_time = (
                event.scheduled_at
            )

            execution = (
                self._apply_event(
                    event
                )
            )

            executions.append(
                execution
            )

            self.event_history.append(
                execution
            )

        # Après avoir exécuté tous les événements,
        # on avance jusqu'au temps demandé.
        self.current_time = target_time

        return executions

    # ========================================================
    # EVENT EXECUTION
    # ========================================================

    def _apply_event(
        self,
        event: MarketEvent,
    ) -> EventExecution:
        """
        Applique effectivement un événement au monde.
        """

        user = self.users.get(
            event.user_id
        )

        if user is None:

            return EventExecution(
                event_id=event.id,
                event_type=event.event_type,
                user_id=event.user_id,
                executed_at=self.current_time,

                success=False,

                message=(
                    "Utilisateur introuvable."
                ),
            )

        try:

            # ----------------------------------------
            # USER ONLINE
            # ----------------------------------------

            if (
                event.event_type
                == EventType.USER_ONLINE
            ):

                user.online = True

                return self._success(
                    event,
                    "Utilisateur maintenant online."
                )

            # ----------------------------------------
            # USER OFFLINE
            # ----------------------------------------

            if (
                event.event_type
                == EventType.USER_OFFLINE
            ):

                user.online = False

                return self._success(
                    event,
                    "Utilisateur maintenant offline."
                )

            # ----------------------------------------
            # RESOURCE ADDED
            # ----------------------------------------

            if (
                event.event_type
                == EventType.RESOURCE_ADDED
            ):

                user.resources.append(
                    event.resource
                )

                return self._success(
                    event,
                    (
                        "Ressource ajoutée : "
                        f"{event.resource.resource_type} "
                        f"{event.resource.quantity} "
                        f"{event.resource.unit}."
                    ),
                )

            # ----------------------------------------
            # RESOURCE REMOVED / EXPIRED
            # ----------------------------------------

            if event.event_type in {
                EventType.RESOURCE_REMOVED,
                EventType.RESOURCE_EXPIRED,
            }:

                return (
                    self._remove_resource(
                        user,
                        event,
                    )
                )

            # ----------------------------------------
            # NEED ADDED
            # ----------------------------------------

            if (
                event.event_type
                == EventType.NEED_ADDED
            ):

                user.needs.append(
                    event.need
                )

                return self._success(
                    event,
                    (
                        "Nouveau besoin ajouté : "
                        f"{event.need.resource_type}."
                    ),
                )

            # ----------------------------------------
            # NEED REMOVED
            # ----------------------------------------

            if (
                event.event_type
                == EventType.NEED_REMOVED
            ):

                return (
                    self._remove_need(
                        user,
                        event,
                    )
                )

            return EventExecution(
                event_id=event.id,
                event_type=event.event_type,
                user_id=event.user_id,
                executed_at=self.current_time,

                success=False,
                message="Type d'événement inconnu.",
            )

        except Exception as exc:

            return EventExecution(
                event_id=event.id,
                event_type=event.event_type,
                user_id=event.user_id,
                executed_at=self.current_time,

                success=False,

                message=f"Erreur : {exc}",
            )

    # ========================================================
    # INTERNAL HELPERS
    # ========================================================

    def _remove_resource(
        self,
        user: User,
        event: MarketEvent,
    ) -> EventExecution:

        resource = next(
            (
                resource
                for resource in user.resources

                if (
                    resource.id
                    == event.resource_id
                )
            ),
            None,
        )

        if resource is None:

            return EventExecution(
                event_id=event.id,
                event_type=event.event_type,
                user_id=user.id,
                executed_at=self.current_time,

                success=False,

                message=(
                    "Ressource introuvable."
                ),
            )

        # Aucun quantity donné :
        # on retire toute la ressource.
        if event.quantity is None:

            user.resources.remove(
                resource
            )

            return self._success(
                event,
                (
                    "Ressource supprimée : "
                    f"{resource.resource_type}."
                ),
            )

        if event.quantity > resource.quantity:

            return EventExecution(
                event_id=event.id,
                event_type=event.event_type,
                user_id=user.id,
                executed_at=self.current_time,

                success=False,

                message=(
                    "Quantité à retirer supérieure "
                    "à la quantité disponible."
                ),
            )

        # Si toute la quantité est retirée,
        # on supprime complètement l'objet.
        if event.quantity == resource.quantity:

            user.resources.remove(
                resource
            )

        else:

            resource.quantity -= (
                event.quantity
            )

        return self._success(
            event,
            (
                f"{event.quantity} "
                f"{resource.unit} retirés de "
                f"{resource.resource_type}."
            ),
        )

    def _remove_need(
        self,
        user: User,
        event: MarketEvent,
    ) -> EventExecution:

        need = next(
            (
                need
                for need in user.needs

                if need.id == event.need_id
            ),
            None,
        )

        if need is None:

            return EventExecution(
                event_id=event.id,
                event_type=event.event_type,
                user_id=user.id,
                executed_at=self.current_time,

                success=False,

                message="Besoin introuvable.",
            )

        user.needs.remove(
            need
        )

        return self._success(
            event,
            (
                "Besoin supprimé : "
                f"{need.resource_type}."
            ),
        )

    def _success(
        self,
        event: MarketEvent,
        message: str,
    ) -> EventExecution:

        return EventExecution(
            event_id=event.id,
            event_type=event.event_type,
            user_id=event.user_id,

            executed_at=self.current_time,

            success=True,
            message=message,
        )