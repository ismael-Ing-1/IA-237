"""Tests du raccordement API/orchestrateur. À exécuter depuis la racine du projet.

Le test d'exécution utilise un faux settlement explicite : il vérifie la barrière
humaine et l'unicité, pas la transaction d'inventaire de market/exchange.py.
"""
from __future__ import annotations

import json
import time
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api import main as api
from app.models.resource import Resource
from app.simulation.scenario_loader import (
    ScenarioDefinition, load_scenario, prepare_scenario,
)


@pytest.fixture
def client():
    api.orchestrator.step_delay = 0.01
    with TestClient(api.app) as test_client:
        assert test_client.delete("/dev/reset").status_code == 200
        yield test_client
        assert test_client.delete("/dev/reset").status_code == 200


def settled(client, negotiation_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        result = client.get(f"/negotiations/{negotiation_id}").json()
        if result["status"] not in {"open", "negotiating"}:
            return result
        time.sleep(0.01)
    pytest.fail("Agent run did not stop within 5 seconds")


def run_bilateral(client):
    response = client.post("/dev/scenarios/bilateral/run")
    assert response.status_code == 200, response.text
    negotiation_id = response.json()["initial_step"]["negotiation"]["id"]
    return negotiation_id, settled(client, negotiation_id)


def test_single_world_reference_and_reset(client):
    identity = id(api.world)
    assert api.orchestrator.world is api.app.state.world is api.world
    assert client.post("/dev/scenarios/bilateral/load").status_code == 200
    assert id(api.world) == identity
    assert api.world.registry.get_public_profile("alice") is not None
    assert client.delete("/dev/reset").status_code == 200
    assert id(api.world) == identity
    assert client.get("/simulation/state").json()["users"] == []


def test_ws_envelope_and_reconnect_resync(client):
    with client.websocket_connect("/ws", headers={"origin": "http://localhost:5173"}) as ws:
        first = ws.receive_json()
        assert first["type"] == "connected"
        assert set(first) == {"event_id", "type", "timestamp", "user_id", "entity_id", "payload"}
        assert first["user_id"] is None and first["entity_id"] is None
        assert ws.receive_json()["type"] == "market_updated"
        ws.send_text("ping")
        assert ws.receive_json()["payload"]["message"] == "pong"


def test_ws_origin_validation(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws", headers={"origin": "https://untrusted.example"}):
            pass


def test_bilateral_waits_for_human_and_streams_events(client):
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "connected"
        assert ws.receive_json()["type"] == "market_updated"
        negotiation_id, negotiation = run_bilateral(client)
        assert negotiation["status"] == "waiting_human"
        types = []
        for _ in range(40):
            message = ws.receive_json()
            types.append(message["type"])
            assert "preferred_partners" not in message["payload"]
            if message["type"] == "human_approval_required":
                assert message["entity_id"] == negotiation_id
                break
        assert "offer_sent" in types and "offer_accepted" in types
        assert "human_approval_required" in types
        assert "exchange_completed" not in types
        alice = client.get("/users/alice/dashboard").json()
        assert alice["resources"][0]["quantity"] == 40
        assert client.post(f"/negotiations/{negotiation_id}/execute").status_code == 409


def test_duplicate_objective_is_rejected(client):
    run_bilateral(client)
    goal = load_scenario("bilateral").goal
    response = client.post("/agents/alice/pursue", json=goal.model_dump(mode="json", exclude={"user_id"}))
    assert response.status_code == 409


def test_any_user_ids_work(client):
    scenario = load_scenario("bilateral").model_dump(mode="json")
    mapping = {"alice": "organization-701", "bob": "organization-902"}
    for user in scenario["users"]:
        user["id"] = mapping[user["id"]]
        user["name"] = "Renamed organization " + user["id"]
        user["preferred_partners"] = [mapping[p] for p in user["preferred_partners"]]
        assert client.post("/users", json=user).status_code == 201
    goal = scenario["goal"]
    owner = mapping[goal.pop("user_id")]
    response = client.post(f"/agents/{owner}/pursue", json=goal)
    assert response.status_code == 200, response.text
    negotiation = settled(client, response.json()["negotiation"]["id"])
    assert negotiation["status"] == "waiting_human"
    assert set(negotiation["participant_ids"]) == set(mapping.values())


def test_coalition_is_proposed_not_executed(client):
    response = client.post("/dev/scenarios/coalition/run")
    assert response.status_code == 200, response.text
    negotiation_id = response.json()["initial_step"]["negotiation"]["id"]
    assert settled(client, negotiation_id)["status"] in {"failed", "rejected"}
    coalitions = client.get("/coalitions/alice").json()
    assert len(coalitions) >= 1
    proposal = coalitions[0]["proposal"]
    assert set(proposal["participant_ids"]) == {"alice", "bob", "charlie"}
    assert len(proposal["transfers"]) == 3
    assert client.get("/simulation/state").json()["completed_negotiations"] == []
    assert client.get("/users/alice/dashboard").json()["resources"][0]["quantity"] == 40


def test_seeded_negotiation_and_mediator(client):
    response = client.post("/dev/scenarios/negociation/load")
    assert response.status_code == 200, response.text
    negotiation_id = response.json()["seeded_negotiation_id"]
    before = client.get(f"/negotiations/{negotiation_id}").json()
    assert len(before["offers"]) == 2
    assert before["offers"][0]["status"] == "countered"
    response = client.post(f"/negotiations/{negotiation_id}/mediate")
    assert response.status_code == 200, response.text
    assert response.json()["action"] == "suggest_counter"
    assert client.get(f"/negotiations/{negotiation_id}").json() == before
    assert client.post(f"/negotiations/{negotiation_id}/resume").status_code == 200
    assert settled(client, negotiation_id)["status"] == "waiting_human"


def test_virtual_time_and_events(client):
    assert client.post("/dev/scenarios/showcase/load").status_code == 200
    response = client.post("/simulation/advance", json={"minutes": 10})
    assert response.status_code == 200, response.text
    assert len(response.json()["executed_events"]) == 1
    assert response.json()["executed_events"][0]["success"] is True
    david = client.get("/users/david/dashboard").json()
    assert sum(r["quantity"] for r in david["resources"] if r["resource_type"] == "H100") == 12


def test_showcase_run_rejects_missing_goal_without_erasing_world(client):
    assert client.post("/dev/scenarios/bilateral/load").status_code == 200
    before = client.get("/simulation/state").json()
    assert client.post("/dev/scenarios/showcase/run").status_code == 400
    assert client.get("/simulation/state").json() == before


def test_bad_scenario_does_not_reset_existing_world(client):
    assert client.post("/dev/scenarios/bilateral/load").status_code == 200
    before = client.get("/simulation/state").json()
    assert client.post("/dev/scenarios/missing-fixture/load").status_code == 404
    assert client.get("/simulation/state").json() == before
    with pytest.raises(ValueError):
        load_scenario("../bilateral")
    data = load_scenario("bilateral").model_dump(mode="json")
    data["users"].append(deepcopy(data["users"][0]))
    with pytest.raises(ValueError):
        ScenarioDefinition.model_validate(data)
    assert client.get("/simulation/state").json() == before


def test_reset_awaits_background_workers(client):
    api.orchestrator.step_delay = 2
    assert client.post("/dev/scenarios/bilateral/run").status_code == 200
    assert api.orchestrator.running_count == 1
    assert client.delete("/dev/reset").status_code == 200
    assert api.orchestrator.running_count == 0
    state = client.get("/simulation/state").json()
    assert state["users"] == [] and state["active_negotiations"] == []


def test_no_double_execution_with_fake_settlement(client, monkeypatch):
    negotiation_id, negotiation = run_bilateral(client)
    assert client.post(f"/negotiations/{negotiation_id}/approve").status_code == 200
    calls = []

    def fake_settlement(identifier):
        # Test explicite de l'orchestration, PAS du transfert des ressources.
        calls.append(identifier)
        item = api.world.active_negotiations.pop(identifier)
        api.world.completed_negotiations[identifier] = item
        return True

    monkeypatch.setattr(api.world, "execute_negotiation", fake_settlement)
    assert client.post(f"/negotiations/{negotiation_id}/execute").status_code == 200
    assert client.post(f"/negotiations/{negotiation_id}/execute").status_code == 409
    assert calls == [negotiation_id]
    assert api.reputation.get_record("alice").successful_transactions == 1
    assert api.reputation.get_record("alice").delivered_on_time == 0


def test_split_offer_does_not_bypass_limit(client):
    assert client.post("/dev/scenarios/bilateral/load").status_code == 200
    goal = load_scenario("bilateral").goal.model_dump(mode="json", exclude={"user_id"})
    goal["offered_resources"] = [
        {"resource_type": "STORAGE", "quantity": 10, "unit": "TB-day"},
        {"resource_type": "STORAGE", "quantity": 10, "unit": "TB-day"},
    ]
    response = client.post("/agents/alice/pursue", json=goal)
    assert response.status_code == 400
    assert client.get("/simulation/state").json()["active_negotiations"] == []
