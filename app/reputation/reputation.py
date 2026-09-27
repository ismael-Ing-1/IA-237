# app/reputation/reputation.py

from __future__ import annotations

from enum import Enum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class ReputationEventType(str, Enum):
    """
    Types d'événements pouvant influencer
    la réputation d'un utilisateur.
    """

    TRANSACTION_SUCCESS = "transaction_success"
    TRANSACTION_FAILED = "transaction_failed"
    TRANSACTION_CANCELLED = "transaction_cancelled"

    DELIVERED_ON_TIME = "delivered_on_time"
    DELIVERED_LATE = "delivered_late"


class ReputationRecord(BaseModel):
    """
    Historique agrégé de la réputation
    d'un utilisateur.
    """

    model_config = ConfigDict(
        validate_assignment=True
    )

    user_id: str

    successful_transactions: int = Field(
        default=0,
        ge=0,
    )

    failed_transactions: int = Field(
        default=0,
        ge=0,
    )

    cancelled_transactions: int = Field(
        default=0,
        ge=0,
    )

    delivered_on_time: int = Field(
        default=0,
        ge=0,
    )

    delivered_late: int = Field(
        default=0,
        ge=0,
    )

    @property
    def total_transactions(self) -> int:
        return (
            self.successful_transactions
            + self.failed_transactions
            + self.cancelled_transactions
        )


class ReputationManager:
    """
    Service central chargé de calculer
    et stocker la réputation des utilisateurs.

    Le score est toujours compris entre 0 et 1.

    1.0 = excellente réputation
    0.0 = très mauvaise réputation
    """

    DEFAULT_SCORE = 0.5

    def __init__(self):

        self._records: dict[
            str,
            ReputationRecord
        ] = {}

    def reset(self) -> None:
        """Vide les compteurs en conservant cette instance de service."""
        self._records.clear()

    def replace_records(self, records: list[ReputationRecord]) -> None:
        """Import de scénario : tout valider AVANT de remplacer les compteurs."""
        prepared: dict[str, ReputationRecord] = {}
        for record in records:
            validated = ReputationRecord.model_validate(record.model_dump())
            if validated.user_id in prepared:
                raise ValueError("Duplicate user in reputation records.")
            prepared[validated.user_id] = validated
        self._records.clear()
        self._records.update(prepared)

    # ========================================================
    # RECORD MANAGEMENT
    # ========================================================

    def register_user(
        self,
        user_id: str,
    ) -> ReputationRecord:
        """
        Enregistre un utilisateur.

        Si l'utilisateur existe déjà,
        retourne simplement son record.
        """

        if user_id not in self._records:

            self._records[user_id] = (
                ReputationRecord(
                    user_id=user_id
                )
            )

        return self._records[user_id]

    def get_record(
        self,
        user_id: str,
    ) -> ReputationRecord:
        """
        Retourne le record d'un utilisateur.

        Un utilisateur inconnu est automatiquement
        créé avec une réputation neutre.
        """

        return self.register_user(
            user_id
        )

    # ========================================================
    # EVENTS
    # ========================================================

    def record_event(
        self,
        user_id: str,
        event_type: ReputationEventType,
    ) -> None:
        """
        Enregistre un événement affectant
        la réputation.
        """

        record = self.get_record(
            user_id
        )

        if (
            event_type
            == ReputationEventType.TRANSACTION_SUCCESS
        ):

            record.successful_transactions += 1

        elif (
            event_type
            == ReputationEventType.TRANSACTION_FAILED
        ):

            record.failed_transactions += 1

        elif (
            event_type
            == ReputationEventType.TRANSACTION_CANCELLED
        ):

            record.cancelled_transactions += 1

        elif (
            event_type
            == ReputationEventType.DELIVERED_ON_TIME
        ):

            record.delivered_on_time += 1

        elif (
            event_type
            == ReputationEventType.DELIVERED_LATE
        ):

            record.delivered_late += 1

        else:

            raise ValueError(
                f"Type d'événement inconnu : "
                f"{event_type}"
            )

    # ========================================================
    # CONVENIENCE METHODS
    # ========================================================

    def record_success(
        self,
        user_id: str,
        delivered_on_time: bool = True,
    ) -> None:
        """
        Enregistre une transaction réussie.

        Peut également enregistrer si la livraison
        a été effectuée à temps.
        """

        self.record_event(
            user_id,
            ReputationEventType.TRANSACTION_SUCCESS,
        )

        if delivered_on_time:

            self.record_event(
                user_id,
                ReputationEventType.DELIVERED_ON_TIME,
            )

        else:

            self.record_event(
                user_id,
                ReputationEventType.DELIVERED_LATE,
            )

    def record_failure(
        self,
        user_id: str,
    ) -> None:

        self.record_event(
            user_id,
            ReputationEventType.TRANSACTION_FAILED,
        )

    def record_cancellation(
        self,
        user_id: str,
    ) -> None:

        self.record_event(
            user_id,
            ReputationEventType.TRANSACTION_CANCELLED,
        )

    # ========================================================
    # SCORE
    # ========================================================

    def get_score(
        self,
        user_id: str,
    ) -> float:
        """
        Retourne un score entre 0 et 1.

        Le score combine :

        - réussite des transactions : 70 %
        - respect des délais : 30 %

        Les annulations comptent comme une
        demi-défaillance.
        """

        record = self.get_record(
            user_id
        )

        if record.total_transactions == 0:

            return self.DEFAULT_SCORE

        # ----------------------------------------
        # TRANSACTION SCORE
        # ----------------------------------------

        transaction_points = (
            record.successful_transactions
            + 0.5
            * record.cancelled_transactions
        )

        transaction_score = (
            transaction_points
            / record.total_transactions
        )

        # ----------------------------------------
        # DELIVERY SCORE
        # ----------------------------------------

        total_deliveries = (
            record.delivered_on_time
            + record.delivered_late
        )

        if total_deliveries == 0:

            delivery_score = (
                self.DEFAULT_SCORE
            )

        else:

            delivery_score = (
                record.delivered_on_time
                / total_deliveries
            )

        # ----------------------------------------
        # FINAL SCORE
        # ----------------------------------------

        score = (
            0.70 * transaction_score
            + 0.30 * delivery_score
        )

        return round(
            max(
                0.0,
                min(
                    1.0,
                    score,
                ),
            ),
            3,
        )

    # ========================================================
    # COMPARISON
    # ========================================================

    def compare_users(
        self,
        user_a_id: str,
        user_b_id: str,
    ) -> str | None:
        """
        Retourne l'ID de l'utilisateur
        ayant la meilleure réputation.

        Retourne None en cas d'égalité.
        """

        score_a = self.get_score(
            user_a_id
        )

        score_b = self.get_score(
            user_b_id
        )

        if score_a > score_b:
            return user_a_id

        if score_b > score_a:
            return user_b_id

        return None

    def rank_users(
        self,
        user_ids: list[str],
    ) -> list[
        tuple[str, float]
    ]:
        """
        Classe les utilisateurs du meilleur
        score au moins bon.

        Exemple :

        [
            ("bob", 0.95),
            ("charlie", 0.72),
            ("david", 0.51)
        ]
        """

        ranked = [
            (
                user_id,
                self.get_score(
                    user_id
                ),
            )
            for user_id in user_ids
        ]

        return sorted(
            ranked,
            key=lambda item: item[1],
            reverse=True,
        )