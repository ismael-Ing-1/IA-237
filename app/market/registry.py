# app/market/registry.py

from __future__ import annotations

from app.models import User, PublicUserProfile, Resource


class MarketRegistry:
    """
    Registre central des utilisateurs participant au marché.

    Le registry connaît les objets User en interne,
    mais n'expose aux autres composants que des PublicUserProfile.

    Cela permet d'éviter de révéler :
    - les quantités exactes de ressources ;
    - les contraintes privées ;
    - les préférences ;
    - les limites de négociation.
    """

    def __init__(self) -> None:
        self._users: dict[str, User] = {}

    # ------------------------------------------------------------------
    # REGISTRATION
    # ------------------------------------------------------------------

    def register_user(self, user: User) -> None:
        """
        Enregistre un utilisateur dans le marché.

        Si l'utilisateur existe déjà, son profil est remplacé
        par la nouvelle version.
        """

        self._users[user.id] = user

    def unregister_user(self, user_id: str) -> bool:
        """
        Retire un utilisateur du marché.

        Retourne True si l'utilisateur existait,
        False sinon.
        """

        if user_id not in self._users:
            return False

        del self._users[user_id]
        return True

    # ------------------------------------------------------------------
    # PUBLIC INFORMATION
    # ------------------------------------------------------------------

    def get_public_profile(
        self,
        user_id: str
    ) -> PublicUserProfile | None:
        """
        Retourne uniquement le profil public d'un utilisateur.

        Les données privées du User ne sont jamais exposées ici.
        """

        user = self._users.get(user_id)

        if user is None:
            return None

        return user.to_public_profile()

    def list_public_profiles(self) -> list[PublicUserProfile]:
        """
        Retourne tous les profils publics enregistrés.
        """

        return [
            user.to_public_profile()
            for user in self._users.values()
        ]

    def list_online_users(self) -> list[PublicUserProfile]:
        """
        Retourne uniquement les utilisateurs actuellement en ligne.
        """

        return [
            user.to_public_profile()
            for user in self._users.values()
            if user.online
        ]

    # ------------------------------------------------------------------
    # RESOURCE DISCOVERY
    # ------------------------------------------------------------------

    def find_providers(
        self,
        resource_type: str
    ) -> list[PublicUserProfile]:
        """
        Recherche les utilisateurs proposant un type de ressource.

        Exemple :

            find_providers("H100")

        peut retourner :

            Bob
            David

        Important :
        la quantité exacte possédée n'est pas révélée.
        """

        resource_type = resource_type.strip().lower()

        providers: list[PublicUserProfile] = []

        for user in self._users.values():

            if not user.online:
                continue

            offers_resource = any(
                resource.resource_type.lower() == resource_type
                and resource.quantity > 0
                for resource in user.resources
            )

            if offers_resource:
                providers.append(
                    user.to_public_profile()
                )

        return providers

    def find_requesters(
        self,
        resource_type: str
    ) -> list[PublicUserProfile]:
        """
        Recherche les utilisateurs demandant un type de ressource.
        """

        resource_type = resource_type.strip().lower()

        requesters: list[PublicUserProfile] = []

        for user in self._users.values():

            if not user.online:
                continue

            wants_resource = any(
                request.resource_type.lower() == resource_type
                for request in user.needs
            )

            if wants_resource:
                requesters.append(
                    user.to_public_profile()
                )

        return requesters

    # ------------------------------------------------------------------
    # INTERNAL ACCESS
    # ------------------------------------------------------------------

    def get_user(
        self,
        user_id: str
    ) -> User | None:
        """
        Retourne l'objet User complet.

        ATTENTION :
        cette méthode est destinée uniquement aux composants internes
        de confiance du backend.

        Elle ne doit jamais être directement exposée :
        - à un autre utilisateur ;
        - au frontend ;
        - au marketplace public.
        """

        return self._users.get(user_id)

    def get_all_users(self) -> dict[str, User]:
        """
        Retourne une copie du dictionnaire des utilisateurs.

        Les objets User restent les mêmes,
        mais le dictionnaire lui-même ne peut pas être modifié
        pour altérer le registry.
        """

        return dict(self._users)


    # ------------------------------------------------------------------
    # RESOURCE UPDATES
    # ------------------------------------------------------------------

    def add_user_resource(
        self,
        user_id: str,
        resource: Resource,
    ) -> Resource:
        user = self.get_user(user_id)
        if user is None:
            raise ValueError(f"Utilisateur {user_id} introuvable.")

        return user.add_resource(resource)

    def increase_user_resource(
        self,
        user_id: str,
        resource_id: str,
        amount: float,
    ) -> Resource:
        user = self.get_user(user_id)
        if user is None:
            raise ValueError(f"Utilisateur {user_id} introuvable.")

        return user.increase_resource_quantity(resource_id, amount)

    def decrease_user_resource(
        self,
        user_id: str,
        resource_id: str,
        amount: float,
    ) -> Resource | None:
        user = self.get_user(user_id)
        if user is None:
            raise ValueError(f"Utilisateur {user_id} introuvable.")

        return user.decrease_resource_quantity(resource_id, amount)

    def set_user_resource_quantity(
        self,
        user_id: str,
        resource_id: str,
        quantity: float,
    ) -> Resource | None:
        user = self.get_user(user_id)
        if user is None:
            raise ValueError(f"Utilisateur {user_id} introuvable.")

        return user.set_resource_quantity(resource_id, quantity)

    # ------------------------------------------------------------------
    # STATUS
    # ------------------------------------------------------------------

    def set_user_online(
        self,
        user_id: str,
        online: bool
    ) -> bool:
        """
        Change le statut online/offline d'un utilisateur.

        Retourne False si l'utilisateur n'existe pas.
        """

        user = self._users.get(user_id)

        if user is None:
            return False

        user.online = online

        return True

    def user_exists(
        self,
        user_id: str
    ) -> bool:
        """
        Vérifie si un utilisateur existe.
        """

        return user_id in self._users

    def count_users(self) -> int:
        """
        Retourne le nombre total d'utilisateurs enregistrés.
        """

        return len(self._users)