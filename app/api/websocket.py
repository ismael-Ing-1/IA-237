"""Flux d'observation du simulateur LOCAL. Pas une API multi-utilisateurs authentifiée."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder

logger = logging.getLogger(__name__)

# Noms déjà reconnus par src/websocket/events.ts.
EVENT_TYPES = frozenset({
    "connected",
    "agent_started",
    "agent_action",
    "agent_notified",
    "agent_stopped",
    "provider_found",
    "market_updated",
    "user_online",
    "user_offline",
    "negotiation_started",
    "negotiation_updated",
    "offer_sent",
    "counter_offer_sent",
    "offer_accepted",
    "offer_rejected",
    "privacy_check_passed",
    "privacy_blocked",
    "coalition_search_started",
    "coalition_search_completed",
    "coalition_found",
    "coalition_selected",
    "coalition_agent_evaluated",
    "coalition_rejected",
    "coalition_human_approval_required",
    "coalition_human_approved",
    "coalition_human_rejected",
    "coalition_approved",
    "coalition_cancelled",
    "coalition_exchange_started",
    "coalition_exchange_completed",
    "coalition_exchange_failed",
    "mediation_started",
    "mediation_suggestion",
    "llm_thinking",
    "llm_decision",
    "llm_shadow_decision",
    "llm_policy_validated",
    "llm_fallback",
    "human_approval_required",
    "human_approved",
    "human_rejected",
    "exchange_started",
    "exchange_completed",
    "exchange_failed",
    "market_event_scheduled",
    "market_event_executed",
    "simulation_time_updated",
    "error",
})


@dataclass(eq=False)
class _Connection:
    socket: WebSocket
    queue: asyncio.Queue[str]
    writer: asyncio.Task[None] | None = field(default=None)


class WebSocketHub:
    """Une file bornée par client ; un seul writer par connexion.

    emit() sérialise immédiatement un instantané, puis le met en file.
    Un navigateur lent ne bloque jamais la boucle de négociation.
    Les messages ne sont pas persistés/rejoués : REST sert à resynchroniser.
    Tous les appels ont lieu sur la boucle asyncio du même worker Uvicorn.
    """

    def __init__(self, *, queue_size: int = 256, send_timeout: float = 5.0):
        if queue_size < 1 or send_timeout <= 0:
            raise ValueError("Invalid WebSocket queue/timeout.")
        self.queue_size = queue_size
        self.send_timeout = send_timeout
        self._connections: set[_Connection] = set()
        self._sequence = 0
        self._epoch = str(uuid4())

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    def _encode(
        self, event_type: str, *, user_id: str | None = None,
        entity_id: str | None = None, payload: dict[str, Any] | None = None,
    ) -> str:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"Unknown realtime event type: {event_type}")
        self._sequence += 1
        event = {
            "event_id": f"{self._epoch}:{self._sequence}",
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "entity_id": entity_id,
            "payload": payload if payload is not None else {},
        }
        # Aucun objet User complet ne doit être passé comme payload.
        return json.dumps(jsonable_encoder(event), ensure_ascii=False, allow_nan=False)

    async def emit(
        self, *, event_type: str, user_id: str | None = None,
        entity_id: str | None = None, payload: dict[str, Any] | None = None,
    ) -> None:
        message = self._encode(
            event_type, user_id=user_id, entity_id=entity_id, payload=payload,
        )
        for connection in tuple(self._connections):
            try:
                connection.queue.put_nowait(message)
            except asyncio.QueueFull:
                # Le writer sera annulé ; sa fermeture déclenchera une reconnexion.
                self._connections.discard(connection)
                if connection.writer is not None:
                    connection.writer.cancel()

    async def _writer(self, connection: _Connection) -> None:
        try:
            while True:
                message = await connection.queue.get()
                await asyncio.wait_for(
                    connection.socket.send_text(message), timeout=self.send_timeout,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.debug("WebSocket writer disconnected", exc_info=True)
        finally:
            self._connections.discard(connection)
            try:
                await asyncio.wait_for(connection.socket.close(code=1012), timeout=1)
            except Exception:
                pass

    async def serve(self, websocket: WebSocket) -> None:
        await websocket.accept()
        connection = _Connection(websocket, asyncio.Queue(self.queue_size))
        # Handshake puis resynchronisation : couvre une reconnexion ayant raté des events.
        connection.queue.put_nowait(self._encode(
            "connected", payload={"message": "Connected to the local demo event stream."},
        ))
        if self.queue_size > 1:
            connection.queue.put_nowait(self._encode(
                "market_updated", payload={"message": "Refresh REST state after connection."},
            ))
        self._connections.add(connection)
        connection.writer = asyncio.create_task(self._writer(connection))
        try:
            while True:
                raw = await websocket.receive_text()
                # Le canal ne permet aucune commande métier ni approbation.
                if raw.strip().lower() == "ping":
                    try:
                        connection.queue.put_nowait(self._encode(
                            "connected", payload={"message": "pong"},
                        ))
                    except asyncio.QueueFull:
                        break
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            self._connections.discard(connection)
            connection.writer.cancel()
            await asyncio.gather(connection.writer, return_exceptions=True)

    async def shutdown(self) -> None:
        connections = tuple(self._connections)
        self._connections.clear()
        tasks = [item.writer for item in connections if item.writer is not None]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


async def serve_websocket(websocket: WebSocket, hub: WebSocketHub) -> None:
    await hub.serve(websocket)
