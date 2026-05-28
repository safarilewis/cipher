from datetime import datetime
from types import SimpleNamespace

from fastapi import BackgroundTasks
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.analysis import create_analysis, latest_analysis
from app.api.sources import select_github_repositories
from app.db import Base
from app.models import AnalysisStatus, GeneratedEvaluation, GitHubRepository, User
from app.schemas import RepositorySelectionIn
from app.services.analysis import (
    ANALYSIS_SCHEMA,
    ANTHROPIC_TOOL_NAME,
    EVALUATION_INSTRUCTIONS,
    assess_signal_completeness,
    build_analysis_payload,
    extract_anthropic_tool_input,
    fallback_analysis,
    generate_analysis,
    generate_with_anthropic,
    infer_career_stage,
    legacy_project_complexity_notes,
    legacy_skill_model,
    limit_code_context_for_prompt,
    floor_delivery_score,
    normalize_overall_score,
    run_analysis,
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
        }
    )
    assert student["stage"] == "student"
    assert student["graduation_proximity"] == "current"

    new_grad = infer_career_stage(
        {
            "sections": [{"kind": "education", "end_date": "2026-01-01"}],
            "github": {"commits": 300},
            "selected_repositories_for_code_review": [],
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
            "sections": [],
        }
    )
    assert with_code["code_quality"]["source"] == "code_context"
    assert with_code["algorithms"]["primary_source"] == "repo_evidence"


def test_algorithms_uses_leetcode_only_when_provided():
    missing = assess_signal_completeness({"github": {"commits": 0}, "selected_repositories_for_code_review": [], "selected_repository_code_context": [], "sections": []})
    unavailable = assess_signal_completeness({"github": {"commits": 0}, "selected_repositories_for_code_review": [], "selected_repository_code_context": [], "leetcode": {"available": False}, "sections": []})
    available = assess_signal_completeness({"github": {"commits": 0}, "selected_repositories_for_code_review": [], "selected_repository_code_context": [], "leetcode": {"available": True, "medium_solved": 80, "hard_solved": 20}, "sections": []})

    assert missing["algorithms"] == {"available": False, "primary_source": "none", "repo_dsa_found": False}
    assert unavailable["algorithms"] == {"available": False, "primary_source": "none", "repo_dsa_found": False}
    assert available["algorithms"] == {"available": True, "primary_source": "leetcode", "repo_dsa_found": False}
    assert "leetcode_strength" not in available["algorithms"]


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
        raw={"recent_commits": [{"sha": "abc123", "message": "Ship parser", "authored_at": "2026-05-01T00:00:00Z", "url": None}]},
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
    assert payload["selected_repositories_for_code_review"][0]["recent_commits"][0]["message"] == "Ship parser"
    assert "leetcode" not in payload
    assert payload["career_stage"]["stage"] in {"student", "early", "new_grad"}
    assert payload["signal_completeness"]["code_quality"]["source"] == "code_context"


def test_build_payload_includes_leetcode_only_when_snapshot_exists():
    user = SimpleNamespace(name="Ada", headline="Builder", career_stage_override=None)
    snapshot = SimpleNamespace(total_solved=42, easy_solved=20, medium_solved=18, hard_solved=4, ranking=12345)

    payload = build_analysis_payload(user, [], snapshot, [], [])

    assert payload["leetcode"]["available"] is True
    assert payload["leetcode"]["total_solved"] == 42
    assert payload["signal_completeness"]["algorithms"]["primary_source"] == "leetcode"


def test_fallback_and_legacy_mapping_keep_old_shape_available():
    payload = {
        "github": {"repository_count": 2, "commits": 8},
        "sections": [],
        "selected_repositories_for_code_review": [],
        "selected_repository_code_context": [],
        "career_stage": {"stage": "early", "confidence": "low", "signals_used": [], "graduation_proximity": "unknown"},
        "signal_completeness": assess_signal_completeness({"github": {"commits": 8}, "sections": [], "selected_repositories_for_code_review": [], "selected_repository_code_context": []}),
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


def test_instructions_require_peer_calibrated_accuracy():
    assert "PEER CALIBRATION AND ACCURACY" in EVALUATION_INSTRUCTIONS
    assert "students against internship/new-grad peers" in EVALUATION_INSTRUCTIONS
    assert "Prefer conservative, evidence-backed scores" in EVALUATION_INSTRUCTIONS


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


def test_generate_with_anthropic_uses_cached_system_and_tool_use(monkeypatch):
    captured = {}

    class Settings:
        anthropic_api_key = "test-key"
        anthropic_model = "claude-haiku-4-5"

    class FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                content=[
                    SimpleNamespace(
                        type="tool_use",
                        name=ANTHROPIC_TOOL_NAME,
                        input={"ok": True},
                    )
                ]
            )

    class FakeAnthropic:
        def __init__(self, api_key):
            assert api_key == "test-key"
            self.messages = FakeMessages()

    monkeypatch.setattr("app.services.analysis.get_settings", lambda: Settings())
    monkeypatch.setattr("app.services.analysis.Anthropic", FakeAnthropic)
    monkeypatch.setattr("app.services.analysis.build_evaluation_input", lambda payload: "prompt body")

    result = generate_with_anthropic({"summary": "payload"})

    assert captured["model"] == "claude-haiku-4-5"
    assert captured["max_tokens"] == 4096
    assert captured["system"] == [
        {
            "type": "text",
            "text": EVALUATION_INSTRUCTIONS,
            "cache_control": {"type": "ephemeral"},
        }
    ]
    assert captured["tools"] == [
        {
            "name": ANTHROPIC_TOOL_NAME,
            "description": "Submit the structured developer evaluation matching the required schema.",
            "input_schema": ANALYSIS_SCHEMA,
        }
    ]
    assert captured["tool_choice"] == {"type": "tool", "name": ANTHROPIC_TOOL_NAME}
    assert captured["messages"] == [{"role": "user", "content": [{"type": "text", "text": "prompt body"}]}]
    assert result == {"ok": True}


def test_build_payload_includes_temporal_signals():
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
    payload = build_analysis_payload(
        user,
        [repo],
        None,
        [section],
        [{"full_name": "ada/app", "readme": "", "structure_sample": [], "key_files": []}],
    )

    assert "rag_context" not in payload
    assert "temporal_signals" in payload


def test_create_analysis_queues_background_work():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    user = User(id="u-queue", slug="queue", name="Queue")
    db.add(user)
    db.commit()

    background_tasks = BackgroundTasks()
    evaluation = create_analysis(background_tasks, db, user)

    assert evaluation.status == AnalysisStatus.queued
    assert len(background_tasks.tasks) == 1

    active = create_analysis(BackgroundTasks(), db, user)

    assert active.id == evaluation.id
    assert active.status == AnalysisStatus.queued


def test_latest_analysis_keeps_previous_ready_when_newer_run_failed():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    user = User(id="u-latest", slug="latest", name="Latest")
    ready = GeneratedEvaluation(
        id="ready-analysis",
        user_id=user.id,
        status=AnalysisStatus.ready,
        summary="Previous good analysis",
        created_at=datetime(2026, 1, 1),
    )
    failed = GeneratedEvaluation(
        id="failed-analysis",
        user_id=user.id,
        status=AnalysisStatus.failed,
        error="Provider timed out",
        created_at=datetime(2026, 1, 2),
    )
    db.add_all([user, ready, failed])
    db.commit()

    latest = latest_analysis(db, user)

    assert latest.id == "ready-analysis"


def test_latest_analysis_returns_active_run_before_previous_ready():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    user = User(id="u-active", slug="active", name="Active")
    ready = GeneratedEvaluation(id="ready-analysis", user_id=user.id, status=AnalysisStatus.ready, created_at=datetime(2026, 1, 1))
    running = GeneratedEvaluation(id="running-analysis", user_id=user.id, status=AnalysisStatus.running, created_at=datetime(2026, 1, 2))
    db.add_all([user, ready, running])
    db.commit()

    latest = latest_analysis(db, user)

    assert latest.id == "running-analysis"


def test_repository_selection_queues_embedding_precompute(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    user = User(id="u-select", slug="select", name="Select")
    repo = GitHubRepository(
        id="r-select",
        user_id="u-select",
        full_name="select/app",
        code_analysis_snapshot={"readme": "README", "key_files": [{"path": "app/main.py", "content": "print('hi')"}]},
    )
    db.add_all([user, repo])
    db.commit()

    scheduled = []

    background_tasks = BackgroundTasks()
    monkeypatch.setattr("app.api.sources.precompute_repo_embeddings_background", lambda user_id, repository_ids: scheduled.append((user_id, repository_ids)))

    selected = select_github_repositories(RepositorySelectionIn(repository_ids=["r-select"]), background_tasks, db, user)

    assert selected[0].selected_for_analysis is True
    assert len(background_tasks.tasks) == 1

    background_tasks.tasks[0].func(*background_tasks.tasks[0].args, **background_tasks.tasks[0].kwargs)

    assert scheduled == [("u-select", ["r-select"])]


def test_run_analysis_does_not_call_rag_during_evaluation(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    user = User(id="u1", slug="ada", name="Ada")
    repo = GitHubRepository(
        id="r1",
        user_id="u1",
        full_name="ada/app",
        selected_for_analysis=True,
        code_analysis_snapshot={
            "full_name": "ada/app",
            "readme": "README",
            "structure_sample": ["app/main.py"],
            "key_files": [{"path": "app/main.py", "content": "print('hi')"}],
        },
    )
    evaluation = GeneratedEvaluation(id="e1", user_id="u1", status=AnalysisStatus.queued)
    db.add_all([user, repo, evaluation])
    db.commit()

    generated = {
        "summary": "Analysis completed.",
        "skill_model": {
            "code_quality": {"score": None, "confidence": "low", "stage_context": "", "basis": [], "prose": ""},
            "delivery": {"score": None, "confidence": "low", "stage_context": "", "basis": [], "prose": "", "trend": "unknown"},
            "algorithms": {"score": None, "confidence": "low", "stage_context": "", "basis": [], "prose": "", "source": "insufficient"},
            "overall": {"score": None, "confidence": "low", "percentile_note": "", "scope_stage": "unknown", "scope_label": "Insufficient candidate"},
        },
        "career_stage": {"stage": "early", "confidence": "low", "signals_used": [], "graduation_proximity": "unknown"},
        "signal_completeness": {
            "code_quality": {"available": True, "source": "code_context", "repos_reviewed": 1, "confidence": "high"},
            "delivery": {"available": False, "commit_coverage": "summary_only", "recency": "unknown"},
            "algorithms": {"available": False, "primary_source": "none", "repo_dsa_found": False},
            "profile_depth": {"manual_sections": 0, "has_experience": False, "has_education": False, "has_projects": False},
        },
        "repository_evaluations": [],
        "strengths": [],
        "growth_areas": [],
        "evidence_highlights": [],
        "recruiter_copy": "",
    }

    captured_payload = {}

    def fake_generate(payload):
        captured_payload.update(payload)
        return generated

    monkeypatch.setattr("app.services.analysis.generate_analysis", fake_generate)

    result = run_analysis(db, user, evaluation)

    assert result.status == AnalysisStatus.ready
    assert result.summary == "Analysis completed."
    assert "rag_context" not in captured_payload


def test_extract_anthropic_tool_input_returns_matching_tool_block():
    response = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="ignored"),
            SimpleNamespace(type="tool_use", name=ANTHROPIC_TOOL_NAME, input={"ok": True}),
        ]
    )

    assert extract_anthropic_tool_input(response, ANTHROPIC_TOOL_NAME) == {"ok": True}


def test_extract_anthropic_tool_input_raises_when_missing():
    response = SimpleNamespace(content=[SimpleNamespace(type="text", text="no tool")])

    import pytest

    with pytest.raises(ValueError):
        extract_anthropic_tool_input(response, ANTHROPIC_TOOL_NAME)


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
