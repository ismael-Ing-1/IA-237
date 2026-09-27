import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_backend_websocket_knows_every_orchestrator_event():
    orchestrator = (ROOT / "app/agents/orchestrator.py").read_text()
    websocket = (ROOT / "app/api/websocket.py").read_text()

    emitted = set(re.findall(
        r'self\._emit\(\s*"([a-z_]+)"',
        orchestrator,
    ))

    declared_block = re.search(
        r"EVENT_TYPES\s*=\s*frozenset\(\{(.*?)\}\)",
        websocket,
        re.S,
    )
    assert declared_block is not None

    declared = set(re.findall(
        r'"([a-z_]+)"',
        declared_block.group(1),
    ))

    assert emitted <= declared, (
        "Missing realtime event types: "
        + ", ".join(sorted(emitted - declared))
    )
