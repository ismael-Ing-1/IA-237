# app/privacy/guard.py

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, Field

from app.models.offer import Offer
from app.models.user import User

from app.tools.privacy_tools import (
    evaluate_offer_against_private_constraints,
)


class PrivacyAction(str, Enum):
    """
    Action décidée par le PrivacyGuard.
    """

    ALLOW = "allow"
    SANITIZE = "sanitize"
    BLOCK = "block"


class PrivacyViolationType(str, Enum):
    """
    Types de données privées que le système protège.
    """

    PRIVATE_LIMIT = "private_limit"
    EXACT_INVENTORY = "exact_inventory"
    PREFERRED_PARTNERS = "preferred_partners"
    BLOCKED_PARTNERS = "blocked_partners"
    PRIVATE_CONSTRAINT = "private_constraint"
    UNSAFE_OFFER = "unsafe_offer"


class PrivacyViolation(BaseModel):
    """
    Représente une violation détectée.

    On ne stocke volontairement pas la valeur privée
    ayant causé la violation.
    """

    violation_type: PrivacyViolationType
    description: str


class PrivacyCheckResult(BaseModel):
    """
    Résultat produit par le PrivacyGuard.

    Exemple :

        PrivacyCheckResult(
            action=PrivacyAction.SANITIZE,
            safe=True,
            sanitized_message="..."
        )
    """

    action: PrivacyAction

    safe: bool

    violations: list[PrivacyViolation] = Field(
        default_factory=list
    )

    sanitized_message: str | None = None


class PrivacyGuard:
    """
    Barrière de confidentialité entre un agent
    et le monde extérieur.

    Le guard peut :

    - autoriser un message ;
    - nettoyer un message ;
    - bloquer une offre.

    IMPORTANT :

    Il s'agit d'une protection applicative.

    Elle ne constitue pas une garantie cryptographique
    contre toutes les formes possibles de fuite.
    """

    REDACTION = "[PRIVATE]"

    # ========================================================
    # PUBLIC API
    # ========================================================

    def check_message(
        self,
        user: User,
        message: str,
    ) -> PrivacyCheckResult:
        """
        Analyse un message avant son envoi.

        Les catégories actuellement protégées sont :

        - limites privées ;
        - inventaire exact ;
        - partenaires préférés ;
        - partenaires bloqués ;
        - contraintes additionnelles privées.
        """

        if not message.strip():

            return PrivacyCheckResult(
                action=PrivacyAction.ALLOW,
                safe=True,
                sanitized_message=message,
            )

        sanitized = message

        violations: list[
            PrivacyViolation
        ] = []

        # ----------------------------------------------------
        # PRIVATE NEGOTIATION LIMITS
        # ----------------------------------------------------

        (
            sanitized,
            detected,
        ) = self._protect_private_limits(
            user,
            sanitized,
        )

        violations.extend(
            detected
        )

        # ----------------------------------------------------
        # EXACT INVENTORY
        # ----------------------------------------------------

        if not user.constraints.reveal_exact_inventory:

            (
                sanitized,
                detected,
            ) = self._protect_exact_inventory(
                user,
                sanitized,
            )

            violations.extend(
                detected
            )

        # ----------------------------------------------------
        # PREFERRED PARTNERS
        # ----------------------------------------------------

        (
            sanitized,
            detected,
        ) = self._protect_preferred_partners(
            user,
            sanitized,
        )

        violations.extend(
            detected
        )

        # ----------------------------------------------------
        # BLOCKED PARTNERS
        # ----------------------------------------------------

        (
            sanitized,
            detected,
        ) = self._protect_blocked_partners(
            user,
            sanitized,
        )

        violations.extend(
            detected
        )

        # ----------------------------------------------------
        # ADDITIONAL PRIVATE CONSTRAINTS
        # ----------------------------------------------------

        (
            sanitized,
            detected,
        ) = self._protect_additional_constraints(
            user,
            sanitized,
        )

        violations.extend(
            detected
        )

        # ----------------------------------------------------
        # RESULT
        # ----------------------------------------------------

        if not violations:

            return PrivacyCheckResult(
                action=PrivacyAction.ALLOW,
                safe=True,
                violations=[],
                sanitized_message=message,
            )

        return PrivacyCheckResult(
            action=PrivacyAction.SANITIZE,
            safe=True,
            violations=violations,
            sanitized_message=sanitized,
        )

    def check_offer(
        self,
        user: User,
        offer: Offer,
        partner_reputation: float | None = None,
    ) -> PrivacyCheckResult:
        """
        Vérifie qu'une offre respecte les contraintes
        privées de l'utilisateur.

        Contrairement à check_message(), cette fonction
        peut réellement bloquer l'action.
        """

        decision = (
            evaluate_offer_against_private_constraints(
                user=user,
                offer=offer,
                partner_reputation=partner_reputation,
            )
        )

        if decision.allowed:

            return PrivacyCheckResult(
                action=PrivacyAction.ALLOW,
                safe=True,
            )

        violations = [
            PrivacyViolation(
                violation_type=(
                    PrivacyViolationType.UNSAFE_OFFER
                ),
                description=reason,
            )
            for reason in decision.reasons
        ]

        return PrivacyCheckResult(
            action=PrivacyAction.BLOCK,
            safe=False,
            violations=violations,
        )

    def sanitize_message(
        self,
        user: User,
        message: str,
    ) -> str:
        """
        Retourne directement la version sûre
        d'un message.
        """

        result = self.check_message(
            user,
            message,
        )

        return (
            result.sanitized_message
            if result.sanitized_message is not None
            else message
        )

    # ========================================================
    # PRIVATE NEGOTIATION LIMITS
    # ========================================================

    def _protect_private_limits(
        self,
        user: User,
        message: str,
    ) -> tuple[
        str,
        list[PrivacyViolation],
    ]:
        """
        Protège les valeurs de :

            user.constraints.max_quantity_to_give

        Exemple :

            STORAGE -> 20

        Le message :

            "My maximum STORAGE is 20."

        devient :

            "My maximum STORAGE is [PRIVATE]."
        """

        sanitized = message

        violations: list[
            PrivacyViolation
        ] = []

        for (
            resource_type,
            limit,
        ) in (
            user.constraints
            .max_quantity_to_give
            .items()
        ):

            if not self._contains_resource_value(
                sanitized,
                resource_type,
                limit,
            ):
                continue

            sanitized = (
                self._redact_resource_value(
                    sanitized,
                    resource_type,
                    limit,
                )
            )

            violations.append(
                PrivacyViolation(
                    violation_type=(
                        PrivacyViolationType.PRIVATE_LIMIT
                    ),
                    description=(
                        "Private negotiation limit detected "
                        f"for resource {resource_type}."
                    ),
                )
            )

        return (
            sanitized,
            violations,
        )

    # ========================================================
    # INVENTORY
    # ========================================================

    def _protect_exact_inventory(
        self,
        user: User,
        message: str,
    ) -> tuple[
        str,
        list[PrivacyViolation],
    ]:
        """
        Empêche de révéler la quantité exacte
        d'une ressource lorsque :

            reveal_exact_inventory = False
        """

        sanitized = message

        violations: list[
            PrivacyViolation
        ] = []

        for resource in user.resources:

            if not self._contains_resource_value(
                sanitized,
                resource.resource_type,
                resource.quantity,
            ):
                continue

            sanitized = (
                self._redact_resource_value(
                    sanitized,
                    resource.resource_type,
                    resource.quantity,
                )
            )

            violations.append(
                PrivacyViolation(
                    violation_type=(
                        PrivacyViolationType.EXACT_INVENTORY
                    ),
                    description=(
                        "Exact private inventory detected "
                        f"for resource "
                        f"{resource.resource_type}."
                    ),
                )
            )

        return (
            sanitized,
            violations,
        )

    # ========================================================
    # PREFERRED PARTNERS
    # ========================================================

    def _protect_preferred_partners(
        self,
        user: User,
        message: str,
    ) -> tuple[
        str,
        list[PrivacyViolation],
    ]:
        """
        Masque les identifiants présents dans
        preferred_partners.
        """

        sanitized = message

        violations: list[
            PrivacyViolation
        ] = []

        detected = False

        for partner_id in user.preferred_partners:

            if not partner_id:
                continue

            if (
                partner_id.lower()
                not in sanitized.lower()
            ):
                continue

            sanitized = (
                self._replace_case_insensitive(
                    sanitized,
                    partner_id,
                    self.REDACTION,
                )
            )

            detected = True

        if detected:

            violations.append(
                PrivacyViolation(
                    violation_type=(
                        PrivacyViolationType.PREFERRED_PARTNERS
                    ),
                    description=(
                        "Preferred partner information "
                        "was detected."
                    ),
                )
            )

        return (
            sanitized,
            violations,
        )

    # ========================================================
    # BLOCKED PARTNERS
    # ========================================================

    def _protect_blocked_partners(
        self,
        user: User,
        message: str,
    ) -> tuple[
        str,
        list[PrivacyViolation],
    ]:
        """
        Masque les identifiants présents dans
        blocked_partners.
        """

        sanitized = message

        violations: list[
            PrivacyViolation
        ] = []

        detected = False

        for partner_id in user.blocked_partners:

            if not partner_id:
                continue

            if (
                partner_id.lower()
                not in sanitized.lower()
            ):
                continue

            sanitized = (
                self._replace_case_insensitive(
                    sanitized,
                    partner_id,
                    self.REDACTION,
                )
            )

            detected = True

        if detected:

            violations.append(
                PrivacyViolation(
                    violation_type=(
                        PrivacyViolationType.BLOCKED_PARTNERS
                    ),
                    description=(
                        "Blocked partner information "
                        "was detected."
                    ),
                )
            )

        return (
            sanitized,
            violations,
        )

    # ========================================================
    # ADDITIONAL CONSTRAINTS
    # ========================================================

    def _protect_additional_constraints(
        self,
        user: User,
        message: str,
    ) -> tuple[
        str,
        list[PrivacyViolation],
    ]:
        """
        Protège les valeurs présentes dans :

            user.constraints.additional_constraints

        Exemple :

            {
                "maximum_budget": 300,
                "internal_priority": "critical"
            }

        Les valeurs explicites trouvées dans le message
        sont remplacées par [PRIVATE].
        """

        sanitized = message

        violations: list[
            PrivacyViolation
        ] = []

        detected = False

        for (
            _key,
            value,
        ) in (
            user.constraints
            .additional_constraints
            .items()
        ):

            if value is None:
                continue

            # Les booléens sont volontairement ignorés,
            # car "True" et "False" sont trop génériques.
            if isinstance(
                value,
                bool,
            ):
                continue

            value_as_text = str(
                value
            )

            # Les chaînes très courtes risquent
            # de produire beaucoup de faux positifs.
            if (
                isinstance(value, str)
                and len(value.strip()) < 3
            ):
                continue

            if (
                value_as_text.lower()
                not in sanitized.lower()
            ):
                continue

            sanitized = (
                self._replace_case_insensitive(
                    sanitized,
                    value_as_text,
                    self.REDACTION,
                )
            )

            detected = True

        if detected:

            violations.append(
                PrivacyViolation(
                    violation_type=(
                        PrivacyViolationType.PRIVATE_CONSTRAINT
                    ),
                    description=(
                        "Private additional constraint "
                        "was detected."
                    ),
                )
            )

        return (
            sanitized,
            violations,
        )

    # ========================================================
    # TEXT HELPERS
    # ========================================================

    @staticmethod
    def _format_number(
        value: float,
    ) -> list[str]:
        """
        Retourne plusieurs représentations
        textuelles d'un nombre.

        Exemple :

            20.0

        devient :

            ["20.0", "20"]
        """

        representations = {
            str(value),
        }

        if float(value).is_integer():

            representations.add(
                str(int(value))
            )

        return list(
            representations
        )

    def _contains_resource_value(
        self,
        text: str,
        resource_type: str,
        value: float,
    ) -> bool:
        """
        Recherche une valeur numérique proche
        du nom d'une ressource.

        Exemples détectés :

            "20 STORAGE"

            "STORAGE = 20"

            "maximum STORAGE is 20"
        """

        escaped_resource = re.escape(
            resource_type
        )

        for number in self._format_number(
            value
        ):

            escaped_number = re.escape(
                number
            )

            patterns = [
                (
                    rf"\b{escaped_number}\b"
                    rf".{{0,40}}"
                    rf"\b{escaped_resource}\b"
                ),

                (
                    rf"\b{escaped_resource}\b"
                    rf".{{0,40}}"
                    rf"\b{escaped_number}\b"
                ),
            ]

            for pattern in patterns:

                if re.search(
                    pattern,
                    text,
                    flags=(
                        re.IGNORECASE
                        | re.DOTALL
                    ),
                ):
                    return True

        return False

    def _redact_resource_value(
        self,
        text: str,
        resource_type: str,
        value: float,
    ) -> str:
        """
        Remplace uniquement la valeur numérique
        sensible et conserve le type de ressource.

        Exemple :

            "STORAGE maximum is 20"

        devient :

            "STORAGE maximum is [PRIVATE]"
        """

        sanitized = text

        escaped_resource = re.escape(
            resource_type
        )

        for number in self._format_number(
            value
        ):

            escaped_number = re.escape(
                number
            )

            # ------------------------------------------------
            # CAS 1
            #
            # Le nombre apparaît AVANT la ressource.
            #
            # Exemple :
            #
            # "I have 50 STORAGE"
            # ------------------------------------------------

            pattern_before = (
                rf"\b{escaped_number}\b"
                rf"(?=.{{0,40}}"
                rf"\b{escaped_resource}\b)"
            )

            sanitized = re.sub(
                pattern_before,
                self.REDACTION,
                sanitized,
                flags=(
                    re.IGNORECASE
                    | re.DOTALL
                ),
            )

            # ------------------------------------------------
            # CAS 2
            #
            # Le nombre apparaît APRÈS la ressource.
            #
            # Exemple :
            #
            # "My STORAGE limit is 20"
            # ------------------------------------------------

            pattern_after = (
                rf"(\b{escaped_resource}\b"
                rf".{{0,40}}?)"
                rf"\b{escaped_number}\b"
            )

            sanitized = re.sub(
                pattern_after,

                lambda match: (
                    match.group(1)
                    + self.REDACTION
                ),

                sanitized,

                flags=(
                    re.IGNORECASE
                    | re.DOTALL
                ),
            )

        return sanitized

    @staticmethod
    def _replace_case_insensitive(
        text: str,
        target: str,
        replacement: str,
    ) -> str:
        """
        Effectue un remplacement sans tenir
        compte des majuscules/minuscules.
        """

        return re.sub(
            re.escape(target),
            replacement,
            text,
            flags=re.IGNORECASE,
        )