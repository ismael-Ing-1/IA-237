from app.llm.context import public_candidate_context
from app.agents.personal_agent import CandidatePartner


def test_candidate_context_contains_no_private_fields():
    context = public_candidate_context(
        strategy="conservative",
        requested_resource_type="H100",
        candidates=[
            CandidatePartner(
                user_id="bob",
                display_name="Bob",
                reputation=0.9,
                preference_rank=0,
                offered_resource_types=["H100"],
            )
        ],
    )

    serialized = str(context).lower()

    assert "max_quantity_to_give" not in serialized
    assert "blocked_partners" not in serialized
    assert "preferred_partners" not in serialized
    assert "preference_rank" not in serialized
