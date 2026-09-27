import json
from pathlib import Path


def test_open_llm_scenarios_do_not_prescribe_outcomes():
    root = Path(__file__).resolve().parents[1]

    for name in (
        "llm_playground.json",
        "llm_market_choice.json",
        "llm_open_coalition.json",
    ):
        data = json.loads(
            (
                root
                / "scenarios"
                / name
            ).read_text()
        )

        assert "seed_negotiation" not in data
        assert "expected_coalition" not in data
        assert (
            "expected_result"
            not in data.get("demo", {})
        )
        assert data.get("goal") is not None
