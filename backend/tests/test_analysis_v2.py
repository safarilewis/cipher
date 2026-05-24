from types import SimpleNamespace

from app.services.analysis import (
    ANALYSIS_SCHEMA,
    assess_signal_completeness,
    build_analysis_payload,
    fallback_analysis,
    infer_career_stage,
    legacy_project_complexity_notes,
    legacy_skill_model,
)


def test_career_stage_override_wins():
    result = infer_career_stage({"sections": [], "github": {"commits": 0}, "selected_repositories_for_code_review": []}, "senior")
    assert result["stage"] == "senior"
    assert result["confidence"] == "high"
    assert result["signals_used"] == ["user-selected career stage override"]


def test_career_stage_infers_student_and_new_grad():
    student = infer_career_stage(
        {
            "sections": [{"kind": "education", "end_date": None}],
            "github": {"commits": 10},
            "selected_repositories_for_code_review": [],
            "leetcode": {"available": False},
        }
    )
    assert student["stage"] == "student"
    assert student["graduation_proximity"] == "current"

    new_grad = infer_career_stage(
        {
            "sections": [{"kind": "education", "end_date": "2026-01-01"}],
            "github": {"commits": 300},
            "selected_repositories_for_code_review": [],
            "leetcode": {"available": False},
        }
    )
    assert new_grad["stage"] == "new_grad"
    assert new_grad["graduation_proximity"] == "recent"


def test_signal_completeness_distinguishes_metadata_and_code_context():
    metadata_only = assess_signal_completeness(
        {
            "github": {"commits": 12},
            "selected_repositories_for_code_review": [{"full_name": "me/app", "description": "", "pushed_at": "2026-05-01T00:00:00"}],
            "selected_repository_code_context": [],
            "leetcode": {"available": False},
            "sections": [{"kind": "project"}],
        }
    )
    assert metadata_only["code_quality"]["source"] == "metadata_only"
    assert metadata_only["code_quality"]["confidence"] == "medium"
    assert metadata_only["delivery"]["recency"] == "active"

    with_code = assess_signal_completeness(
        {
            "github": {"commits": 12},
            "selected_repositories_for_code_review": [{"full_name": "me/algorithms", "description": "", "pushed_at": "2026-05-01T00:00:00"}],
            "selected_repository_code_context": [{"full_name": "me/algorithms", "readme": "Graph traversal", "structure_sample": ["src/graph.py"], "key_files": []}],
            "leetcode": {"available": False},
            "sections": [],
        }
    )
    assert with_code["code_quality"]["source"] == "code_context"
    assert with_code["algorithms"]["primary_source"] == "repo_evidence"


def test_leetcode_strength_thresholds():
    absent = assess_signal_completeness({"github": {"commits": 0}, "selected_repositories_for_code_review": [], "selected_repository_code_context": [], "leetcode": {"available": False}, "sections": []})
    weak = assess_signal_completeness({"github": {"commits": 0}, "selected_repositories_for_code_review": [], "selected_repository_code_context": [], "leetcode": {"available": True, "medium_solved": 10, "hard_solved": 0}, "sections": []})
    moderate = assess_signal_completeness({"github": {"commits": 0}, "selected_repositories_for_code_review": [], "selected_repository_code_context": [], "leetcode": {"available": True, "medium_solved": 30, "hard_solved": 0}, "sections": []})
    strong = assess_signal_completeness({"github": {"commits": 0}, "selected_repositories_for_code_review": [], "selected_repository_code_context": [], "leetcode": {"available": True, "medium_solved": 80, "hard_solved": 20}, "sections": []})

    assert absent["algorithms"]["leetcode_strength"] == "absent"
    assert weak["algorithms"]["leetcode_strength"] == "weak"
    assert moderate["algorithms"]["leetcode_strength"] == "moderate"
    assert strong["algorithms"]["leetcode_strength"] == "strong"


def test_build_payload_includes_dates_url_and_v2_inputs():
    user = SimpleNamespace(name="Ada", headline="Builder", career_stage_override=None)
    repo = SimpleNamespace(
        full_name="ada/app",
        description="A project",
        language="Python",
        stars=1,
        forks=0,
        commit_count=40,
        all_time_commit_count=140,
        pushed_at=None,
        selected_for_analysis=True,
    )
    section = SimpleNamespace(
        kind="project",
        title="Compiler",
        organization="School",
        start_date="2025-01",
        end_date="2025-05",
        description="Built a parser",
        url="https://example.com",
    )
    payload = build_analysis_payload(user, [repo], None, [section], [{"full_name": "ada/app", "readme": "", "structure_sample": [], "key_files": []}])

    assert payload["sections"][0]["start_date"] == "2025-01"
    assert payload["sections"][0]["url"] == "https://example.com"
    assert payload["selected_repositories_for_code_review"][0]["all_time_commit_count"] == 140
    assert payload["career_stage"]["stage"] in {"student", "early", "new_grad"}
    assert payload["signal_completeness"]["code_quality"]["source"] == "code_context"


def test_fallback_and_legacy_mapping_keep_old_shape_available():
    payload = {
        "github": {"repository_count": 2, "commits": 8},
        "sections": [],
        "selected_repositories_for_code_review": [],
        "selected_repository_code_context": [],
        "leetcode": {"available": False},
        "career_stage": {"stage": "early", "confidence": "low", "signals_used": [], "graduation_proximity": "unknown"},
        "signal_completeness": assess_signal_completeness({"github": {"commits": 8}, "sections": [], "selected_repositories_for_code_review": [], "selected_repository_code_context": [], "leetcode": {"available": False}}),
    }
    fallback = fallback_analysis(payload)

    assert fallback["skill_model"]["code_quality"]["score"] is None
    assert fallback["repository_evaluations"] == []
    assert set(legacy_skill_model(fallback["skill_model"])) == {"code_quality", "delivery", "algorithms"}
    assert legacy_project_complexity_notes([]) == []


def test_v2_schema_has_nested_additional_properties_false():
    def walk(schema):
        if schema.get("type") == "object":
            assert schema.get("additionalProperties") is False
            assert set(schema.get("required", [])) == set(schema.get("properties", {}))
        if "properties" in schema:
            for child in schema["properties"].values():
                walk(child)
        items = schema.get("items")
        if isinstance(items, dict):
            walk(items)

    walk(ANALYSIS_SCHEMA)
