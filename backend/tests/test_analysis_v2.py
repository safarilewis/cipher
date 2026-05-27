from types import SimpleNamespace

from app.services.analysis import (
    ANALYSIS_SCHEMA,
    EVALUATION_INSTRUCTIONS,
    assess_signal_completeness,
    build_analysis_payload,
    fallback_analysis,
    generate_analysis,
    generate_with_anthropic,
    infer_career_stage,
    extract_anthropic_text,
    legacy_project_complexity_notes,
    legacy_skill_model,
    limit_code_context_for_prompt,
    floor_delivery_score,
    normalize_overall_score,
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


def test_limit_code_context_for_prompt_respects_repo_and_char_budgets():
    repos = [
        SimpleNamespace(full_name="me/high-commit", commit_count=500, pushed_at=None),
        SimpleNamespace(full_name="me/medium-commit", commit_count=200, pushed_at=None),
        SimpleNamespace(full_name="me/low-commit", commit_count=10, pushed_at=None),
    ]
    contexts = [
        {"full_name": "me/high-commit", "readme": "a" * 50, "structure_sample": ["src/a.py"], "key_files": [{"path": "src/a.py", "content": "x" * 50}]},
        {"full_name": "me/medium-commit", "readme": "b" * 50, "structure_sample": ["src/b.py"], "key_files": [{"path": "src/b.py", "content": "y" * 50}]},
        {"full_name": "me/low-commit", "readme": "c" * 50, "structure_sample": ["src/c.py"], "key_files": [{"path": "src/c.py", "content": "z" * 50}]},
    ]

    included, omissions = limit_code_context_for_prompt(repos, contexts, max_repos=2, max_chars=240)

    assert len(included) == 2
    assert included[0]["full_name"] == "me/high-commit"
    assert included[0]["key_files"][0]["content"] == "x" * 50
    assert any(item["full_name"] == "me/low-commit" for item in omissions)


def test_generate_analysis_routes_to_openai(monkeypatch):
    class Settings:
        analysis_provider = "openai"

    monkeypatch.setattr("app.services.analysis.get_settings", lambda: Settings())
    monkeypatch.setattr("app.services.analysis.generate_with_openai", lambda payload: {"provider": "openai"})
    monkeypatch.setattr("app.services.analysis.generate_with_anthropic", lambda payload: {"provider": "anthropic"})

    result = generate_analysis({"summary": "payload"})

    assert result["provider"] == "openai"


def test_generate_analysis_routes_to_anthropic(monkeypatch):
    class Settings:
        analysis_provider = "anthropic"

    monkeypatch.setattr("app.services.analysis.get_settings", lambda: Settings())
    monkeypatch.setattr("app.services.analysis.generate_with_openai", lambda payload: {"provider": "openai"})
    monkeypatch.setattr("app.services.analysis.generate_with_anthropic", lambda payload: {"provider": "anthropic"})

    result = generate_analysis({"summary": "payload"})

    assert result["provider"] == "anthropic"


def test_generate_with_anthropic_sends_text_block_message(monkeypatch):
    captured = {}

    class Settings:
        anthropic_api_key = "test-key"
        anthropic_model = "claude-sonnet-4-20250514"

    class FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(content=[SimpleNamespace(type="text", text='{"ok": true}')])

    class FakeAnthropic:
        def __init__(self, api_key):
            assert api_key == "test-key"
            self.messages = FakeMessages()

    monkeypatch.setattr("app.services.analysis.get_settings", lambda: Settings())
    monkeypatch.setattr("app.services.analysis.Anthropic", FakeAnthropic)
    monkeypatch.setattr("app.services.analysis.extract_json_response", lambda text: {"ok": True, "text": text})
    monkeypatch.setattr("app.services.analysis.build_evaluation_input", lambda payload: "prompt body")

    result = generate_with_anthropic({"summary": "payload"})

    assert captured["model"] == "claude-sonnet-4-20250514"
    assert captured["max_tokens"] == 4096
    assert captured["system"] == EVALUATION_INSTRUCTIONS
    assert captured["messages"] == [{"role": "user", "content": [{"type": "text", "text": "prompt body"}]}]
    assert result["ok"] is True


def test_build_payload_includes_rag_and_temporal(monkeypatch):
    # Ensure build_analysis_payload accepts rag_context and includes temporal_signals
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
        created_at=datetime.utcnow(),
        id="r1",
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
    rag_context = {"architecture": []}
    payload = build_analysis_payload(user, [repo], None, [section], [{"full_name": "ada/app", "readme": "", "structure_sample": [], "key_files": []}], rag_context=rag_context)

    assert "rag_context" in payload and payload["rag_context"] == rag_context
    assert "temporal_signals" in payload


def test_extract_anthropic_text_prefers_native_text_property():
    response = SimpleNamespace(text='{"ok": true}', content=[SimpleNamespace(type="text", text='{"ignored": true}')])

    assert extract_anthropic_text(response) == '{"ok": true}'


def test_extract_anthropic_text_joins_text_blocks_when_native_text_missing():
    response = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text='{"ok": '),
            SimpleNamespace(type="text", text='true}'),
        ]
    )

    assert extract_anthropic_text(response) == '{"ok": true}'


def test_normalize_overall_score_reweights_algorithms_lower():
    skill_model = {
        "code_quality": {"score": 80},
        "delivery": {"score": 70},
        "algorithms": {"score": 95},
        "overall": {"score": 999, "confidence": "low", "percentile_note": ""},
    }

    overall = normalize_overall_score(skill_model)

    assert overall["score"] == 78.8
    assert overall["confidence"] == "high"


def test_floor_delivery_score_raises_three_systems_to_minimum_78():
    skill_model = {
        "code_quality": {"score": 72},
        "delivery": {"score": 61, "confidence": "low", "stage_context": "", "basis": [], "prose": ""},
        "algorithms": {"score": 84},
        "overall": {"score": 0, "confidence": "low", "percentile_note": ""},
    }
    repository_evaluations = [
        {"complexity_tier": "system"},
        {"complexity_tier": "system"},
        {"complexity_tier": "system"},
    ]

    updated = floor_delivery_score(skill_model, repository_evaluations)

    assert updated["delivery"]["score"] == 78
    assert updated["delivery"]["confidence"] == "medium"


def test_normalize_overall_score_requires_two_dimensions():
    overall = normalize_overall_score(
        {
            "code_quality": {"score": 80},
            "delivery": {"score": None},
            "algorithms": {"score": None},
            "overall": {"score": 50, "confidence": "high", "percentile_note": ""},
        }
    )

    assert overall["score"] is None
    assert overall["confidence"] == "low"


def test_compute_temporal_signals_empty():
    from app.services.analysis import compute_temporal_signals

    result = compute_temporal_signals([])
    assert result["available"] is False


def test_analyze_repo_architecture_detects_patterns():
    from app.services.analysis import analyze_repo_architecture

    context = {"structure_sample": [
        "backend/app/services/auth.py", "backend/app/models/user.py",
        "frontend/app/page.tsx", ".github/workflows/ci.yml",
        "Dockerfile", "alembic/versions/001_initial.py", "tests/test_auth.py",
    ]}
    result = analyze_repo_architecture(context)
    assert "frontend_backend_split" in result["patterns_detected"]
    assert "layered_architecture" in result["patterns_detected"]
    assert "has_ci" in result["patterns_detected"]
    assert "has_docker" in result["patterns_detected"]
