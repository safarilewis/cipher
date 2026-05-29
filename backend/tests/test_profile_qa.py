from datetime import datetime
from types import SimpleNamespace

from app.services.profile_qa import (
    answer_profile_question,
    fallback_profile_question_answer,
    profile_question_payload,
)


def make_user():
    return SimpleNamespace(name="Ada", slug="ada", headline="Backend engineer")


def make_section():
    return SimpleNamespace(
        kind="experience",
        title="Engineer",
        organization="Acme",
        start_date="2022",
        end_date=None,
        description="Built services",
        url=None,
    )


def make_repo():
    return SimpleNamespace(
        full_name="ada/app",
        description="An app",
        language="Python",
        stars=10,
        forks=2,
        commit_count=50,
        pushed_at=datetime(2026, 1, 1, 12, 0, 0),
        selected_for_analysis=True,
    )


def make_leetcode():
    return SimpleNamespace(total_solved=100, easy_solved=40, medium_solved=45, hard_solved=15, ranking=12345)


def make_evaluation(profile_signal=None):
    return SimpleNamespace(
        profile_signal_snapshot=profile_signal if profile_signal is not None else {},
        summary="Strong backend developer.",
        skill_model_v2={"python": "advanced"},
        career_stage={"stage": "mid"},
        signal_completeness={"score": 0.8},
        repository_evaluations=[{"repo": "ada/app"}],
        strengths=["APIs"],
        growth_areas=["frontend"],
        evidence_highlights=["Shipped a service", "Wrote tests", "Handled scale", "Mentored", "Extra"],
        recruiter_copy="Great hire.",
    )


# ---------------------------------------------------------------------------
# profile_question_payload
# ---------------------------------------------------------------------------


def test_payload_includes_all_sources():
    payload = profile_question_payload(
        make_user(), [make_section()], [make_repo()], make_leetcode(), make_evaluation()
    )
    assert payload["profile"]["slug"] == "ada"
    assert payload["manual_sections"][0]["kind"] == "experience"
    assert payload["repositories"][0]["full_name"] == "ada/app"
    assert payload["repositories"][0]["pushed_at"] == "2026-01-01T12:00:00"
    assert payload["leetcode"]["total_solved"] == 100
    assert payload["analysis"]["summary"] == "Strong backend developer."


def test_payload_handles_missing_optional_data():
    payload = profile_question_payload(make_user(), [], [], None, None)
    assert payload["leetcode"] is None
    assert payload["manual_sections"] == []
    assert payload["repositories"] == []
    assert payload["analysis"]["summary"] is None
    assert payload["analysis"]["recruiter_signal"] == {}


def test_payload_repo_pushed_at_none_when_missing():
    repo = make_repo()
    repo.pushed_at = None
    payload = profile_question_payload(make_user(), [], [repo], None, None)
    assert payload["repositories"][0]["pushed_at"] is None


def test_payload_extracts_recruiter_signal():
    evaluation = make_evaluation(profile_signal={"recruiter": {"hiring_recommendation": {"decision": "recommend"}}})
    payload = profile_question_payload(make_user(), [], [], None, evaluation)
    assert payload["analysis"]["recruiter_signal"]["hiring_recommendation"]["decision"] == "recommend"


# ---------------------------------------------------------------------------
# fallback_profile_question_answer
# ---------------------------------------------------------------------------


def test_fallback_uses_hiring_recommendation_values():
    payload = {
        "analysis": {
            "summary": "A capable engineer.",
            "evidence_highlights": ["a", "b", "c", "d", "e"],
            "recruiter_signal": {"hiring_recommendation": {"decision": "recommend", "confidence": "high"}},
        }
    }
    result = fallback_profile_question_answer("Is she a fit?", payload)
    assert result["recommendation"] == "recommend"
    assert result["confidence"] == "high"
    assert "recommend" in result["answer"]
    # summary + first 4 highlights
    assert result["evidence"][0] == "A capable engineer."
    assert len(result["evidence"]) == 5
    assert len(result["verification_questions"]) == 3


def test_fallback_normalizes_invalid_decision_and_confidence():
    payload = {
        "analysis": {
            "recruiter_signal": {"hiring_recommendation": {"decision": "maybe", "confidence": "very-high"}},
        }
    }
    result = fallback_profile_question_answer("Q?", payload)
    assert result["recommendation"] == "insufficient_evidence"
    assert result["confidence"] == "low"


def test_fallback_handles_empty_payload():
    result = fallback_profile_question_answer("Q?", {})
    assert result["recommendation"] == "insufficient_evidence"
    assert result["evidence"] == ["The public profile has limited generated analysis available."]


def test_fallback_caps_evidence_at_six():
    payload = {
        "analysis": {
            "summary": "Summary line.",
            "evidence_highlights": ["a", "b", "c", "d", "e", "f", "g"],
        }
    }
    result = fallback_profile_question_answer("Q?", payload)
    # summary + up to 4 highlights, then capped at 6 total
    assert len(result["evidence"]) <= 6


# ---------------------------------------------------------------------------
# answer_profile_question (fallback path when no API key)
# ---------------------------------------------------------------------------


def test_answer_profile_question_falls_back_without_api_key(monkeypatch):
    monkeypatch.setattr(
        "app.services.profile_qa.get_settings",
        lambda: SimpleNamespace(openai_api_key=None, openai_model="gpt-5.2"),
    )
    result = answer_profile_question(
        "Is Ada a fit for a backend role?",
        make_user(),
        [make_section()],
        [make_repo()],
        make_leetcode(),
        make_evaluation(),
    )
    assert set(result) == {"answer", "recommendation", "confidence", "evidence", "verification_questions"}
    assert result["recommendation"] in {"recommend", "consider", "hold", "insufficient_evidence"}
