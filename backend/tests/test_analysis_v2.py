from datetime import datetime
from types import SimpleNamespace

from fastapi import BackgroundTasks
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.analysis import create_analysis, latest_analysis
from app.api.sources import precompute_repo_embeddings, select_github_repositories
from app.db import Base
from app.models import AnalysisStatus, GeneratedEvaluation, GitHubRepository, User
from app.schemas import RepositorySelectionIn
from app.services.analysis import (
    ANALYSIS_SCHEMA,
    ANTHROPIC_TOOL_NAME,
    EVALUATION_INSTRUCTIONS,
    assess_signal_completeness,
    build_analysis_payload,
    compact_code_context_for_prompt,
    extract_anthropic_tool_input,
    fallback_analysis,
    generate_analysis,
    generate_with_anthropic,
    infer_career_stage,
    build_profile_signal_snapshot,
    legacy_project_complexity_notes,
    legacy_skill_model,
    limit_code_context_for_prompt,
    normalize_generated_analysis,
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


def test_compact_code_context_sends_readme_plus_four_high_signal_files():
    context = {
        "full_name": "me/app",
        "readme": "r" * 4000,
        "structure_sample": ["README.md", "package.json", "src/services/a.ts"],
        "key_files": [
            {"path": "README.md", "content": "duplicated readme"},
            {"path": "src/features/noise.ts", "content": "n" * 5000},
            {"path": "src/services/billing.ts", "content": "service"},
            {"path": "src/models/user.ts", "content": "model"},
            {"path": "src/api/users.ts", "content": "api"},
            {"path": "tests/profile.test.ts", "content": "test"},
            {"path": "src/components/Profile.tsx", "content": "component"},
            {"path": "src/lib/auth.ts", "content": "lib"},
            {"path": "package.json", "content": "{}"},
            {"path": "src/utils/date.ts", "content": "util"},
        ],
    }

    compacted = compact_code_context_for_prompt(context)
    paths = [item["path"] for item in compacted["key_files"]]

    assert len(paths) == 4
    assert compacted["readme"].startswith("r")
    assert len(compacted["readme"]) < len(context["readme"])
    assert "README.md" not in paths
    assert paths[0] == "package.json"
    assert {"src/api/users.ts", "src/services/billing.ts", "src/models/user.ts"}.issubset(paths)
    assert "tests/profile.test.ts" not in paths


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
            "cache_control": {"type": "ephemeral", "ttl": "1h"},
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

    assert payload["rag_code_context"] == {}
    assert "temporal_signals" in payload


def test_create_analysis_starts_background_work(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    user = User(id="u-queue", slug="queue", name="Queue")
    db.add(user)
    db.commit()

    started = []
    monkeypatch.setattr("app.api.analysis.start_analysis_worker", lambda user_id, evaluation_id: started.append((user_id, evaluation_id)))

    background_tasks = BackgroundTasks()
    evaluation = create_analysis(background_tasks, db, user)

    assert evaluation.status == AnalysisStatus.queued
    assert background_tasks.tasks == []
    assert started == [("u-queue", evaluation.id)]

    active = create_analysis(BackgroundTasks(), db, user)

    assert active.id == evaluation.id
    assert active.status == AnalysisStatus.queued
    assert started == [("u-queue", evaluation.id), ("u-queue", evaluation.id)]


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


def test_repository_precompute_fetches_missing_code_context_before_embedding(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    user = User(id="u-precompute", slug="precompute", name="Precompute")
    repo = GitHubRepository(
        id="r-precompute",
        user_id=user.id,
        full_name="precompute/app",
        code_analysis_snapshot=None,
    )
    db.add_all([user, repo])
    db.commit()

    fetched_context = {
        "full_name": "precompute/app",
        "readme": "README",
        "structure_sample": ["app/main.py"],
        "key_files": [{"path": "app/main.py", "content": "print('hi')"}],
    }
    embedded = []

    monkeypatch.setattr("app.api.sources.repo_has_embeddings", lambda db, user_id, repo_id: False)
    monkeypatch.setattr("app.api.sources.get_github_access_token", lambda db, user: "gh-token")
    monkeypatch.setattr(
        "app.api.sources.fetch_repo_code_context",
        lambda full_name, access_token=None: fetched_context,
    )
    monkeypatch.setattr(
        "app.api.sources.embed_repo_files_report",
        lambda db, user_id, repo_id, code_context: embedded.append((user_id, repo_id, code_context)) or {"chunks_pending": 1, "chunks_stored": 1, "errors": []},
    )

    precompute_repo_embeddings(db, user.id, [repo.id])

    stored_repo = db.get(GitHubRepository, repo.id)
    assert stored_repo.code_analysis_snapshot == fetched_context
    assert embedded == [(user.id, repo.id, fetched_context)]


def test_run_analysis_includes_precomputed_rag_during_evaluation(monkeypatch):
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
    monkeypatch.setattr("app.services.analysis.repo_has_embeddings", lambda db, user_id, repo_id: True)
    monkeypatch.setattr(
        "app.services.analysis.build_rag_context",
        lambda db, user_id, repo_id_to_full_name, top_k_per_query: {
            "code_quality": [
                {
                    "repo": "ada/app",
                    "repo_id": "r1",
                    "file_path": "app/main.py",
                    "chunk_index": 0,
                    "content": "def handler(): return 'ok'",
                }
            ],
            "architecture": [],
            "algorithms": [],
            "tests": [],
        },
    )

    result = run_analysis(db, user, evaluation)

    assert result.status == AnalysisStatus.ready
    assert result.summary == "Analysis completed."
    assert captured_payload["rag_code_context"]["code_quality"][0]["file_path"] == "app/main.py"
    assert captured_payload["rag_embedding_precompute"]["mode"] == "read_existing_only"
    assert captured_payload["rag_embedding_precompute"]["chunks_stored"] == 0
    assert result.profile_signal_snapshot["rag"]["chunk_count"] == 1


def test_run_analysis_skips_embedding_when_chunks_are_missing(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    user = User(id="u-no-embed", slug="no-embed", name="No Embed")
    repo = GitHubRepository(
        id="r-no-embed",
        user_id=user.id,
        full_name="ada/no-embed",
        selected_for_analysis=True,
        code_analysis_snapshot={
            "full_name": "ada/no-embed",
            "readme": "README",
            "structure_sample": ["src/service.py"],
            "key_files": [{"path": "src/service.py", "content": "def handler(): return True"}],
        },
    )
    evaluation = GeneratedEvaluation(id="e-no-embed", user_id=user.id, status=AnalysisStatus.queued)
    db.add_all([user, repo, evaluation])
    db.commit()

    captured_payload = {}

    def fake_generate(payload):
        captured_payload.update(payload)
        return fallback_analysis(payload)

    monkeypatch.setattr("app.services.analysis.generate_analysis", fake_generate)
    monkeypatch.setattr("app.services.analysis.repo_has_embeddings", lambda db, user_id, repo_id: False)
    monkeypatch.setattr(
        "app.services.analysis.build_rag_context",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("RAG should not run without stored chunks")),
    )

    result = run_analysis(db, user, evaluation)

    assert result.status == AnalysisStatus.ready
    assert captured_payload["rag_code_context"] == {}
    assert captured_payload["rag_embedding_precompute"]["mode"] == "read_existing_only"
    assert captured_payload["rag_embedding_precompute"]["missing"] == [{"repo": "ada/no-embed", "reason": "not_indexed"}]
    assert captured_payload["selected_repository_code_context"][0]["key_files"][0]["path"] == "src/service.py"


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


def test_recruiter_copy_prompt_requires_final_recommendation():
    assert "FINAL_RECOMMENDATION:" in EVALUATION_INSTRUCTIONS
    assert "roles/levels they should be considered for" in EVALUATION_INSTRUCTIONS
    assert "possible evaluations or screens needed next" in EVALUATION_INSTRUCTIONS


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


def test_normalize_generated_analysis_defaults_missing_list_fields():
    generated = {
        "summary": "Anthropic returned most fields.",
        "skill_model": {
            "code_quality": {"score": 70},
            "delivery": {"score": 68},
            "algorithms": {"score": None},
            "overall": {"score": None, "confidence": "low", "percentile_note": ""},
        },
        "career_stage": {"stage": "student"},
    }

    normalized = normalize_generated_analysis(generated)

    assert normalized["repository_evaluations"] == []
    assert normalized["strengths"] == []
    assert normalized["growth_areas"] == []
    assert normalized["evidence_highlights"] == []
    assert normalized["recruiter_copy"] == ""


def test_normalize_generated_analysis_filters_bad_repository_items():
    generated = {
        "summary": "Anthropic returned mixed list items.",
        "skill_model": {
            "code_quality": {"score": 70},
            "delivery": {"score": 68},
            "algorithms": {"score": None},
            "overall": {"score": None, "confidence": "low", "percentile_note": ""},
        },
        "career_stage": {"stage": "student"},
        "repository_evaluations": [
            "bad item",
            {"full_name": "ada/app", "complexity_tier": "project", "architecture_notes": "Layered app."},
        ],
    }

    normalized = normalize_generated_analysis(generated)

    assert normalized["repository_evaluations"] == [
        {"full_name": "ada/app", "complexity_tier": "project", "architecture_notes": "Layered app."}
    ]
    assert legacy_project_complexity_notes(["bad item", normalized["repository_evaluations"][0]]) == [
        "ada/app is assessed as project. Layered app."
    ]


def test_normalize_generated_analysis_parses_json_string_fields():
    generated = {
        "summary": "Anthropic returned encoded JSON fields.",
        "skill_model": '{"code_quality":{"score":72},"delivery":{"score":70},"algorithms":{"score":null},"overall":{"score":null,"confidence":"low","percentile_note":""}}',
        "career_stage": '{"stage":"student"}',
        "repository_evaluations": '[{"full_name":"ada/app","complexity_tier":"project","architecture_notes":"Layered app."}]',
    }

    normalized = normalize_generated_analysis(generated)

    assert isinstance(normalized["skill_model"], dict)
    assert normalized["career_stage"] == {"stage": "student"}
    assert normalized["repository_evaluations"][0]["full_name"] == "ada/app"


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


def test_compute_temporal_signals_uses_raw_created_at_when_model_lacks_created_at():
    from app.services.analysis import compute_temporal_signals

    old_repo = SimpleNamespace(
        full_name="ada/c",
        language="C",
        commit_count=10,
        pushed_at=datetime(2024, 1, 1),
        raw={"created_at": "2023-01-01T00:00:00Z"},
    )
    new_repo = SimpleNamespace(
        full_name="ada/py",
        language="Python",
        commit_count=60,
        pushed_at=datetime(2026, 1, 1),
        raw={"created_at": "2026-01-01T00:00:00Z"},
    )

    result = compute_temporal_signals([old_repo, new_repo])

    assert result["available"] is True
    assert result["first_repo_date"].startswith("2023-01-01")
    assert result["language_timeline"][0]["repo"] == "ada/c"


def test_build_profile_signal_snapshot_captures_live_profile_dimensions():
    user = SimpleNamespace(name="Ada", slug="ada", headline="Compiler builder")
    repo = SimpleNamespace(
        full_name="ada/compiler",
        language="Rust",
        commit_count=80,
        all_time_commit_count=120,
        pushed_at=datetime(2026, 5, 1),
        selected_for_analysis=True,
        raw={"created_at": "2025-01-01T00:00:00Z"},
    )
    section = SimpleNamespace(
        kind="project",
        title="Compiler",
        organization="School",
        start_date="2025-01",
        end_date="2025-05",
    )
    payload = {
        "github": {"commits": 80, "repository_count": 1},
        "temporal_signals": {"available": True, "complexity_trend": "growing", "active_years": 1.3},
        "selected_repositories_for_code_review": [
            {"full_name": "ada/compiler", "pushed_at": "2026-05-01T00:00:00", "recent_commits": [{"message": "Add parser"}]}
        ],
        "signal_completeness": {"delivery": {"recency": "active"}},
    }
    generated = {
        "summary": "Rust compiler project with growing maturity.",
        "recruiter_copy": "Ada shows compiler and systems promise.",
        "strengths": ["Systems instincts"],
        "skill_model": {"algorithms": {"source": "repo_evidence", "prose": "Parser work."}},
        "career_stage": {"stage": "student"},
        "signal_completeness": {"code_quality": {"source": "code_context"}},
        "evidence_highlights": ["Cites parser files"],
        "repository_evaluations": [{"specific_code_references": ["src/parser.rs"]}],
    }
    code_context = [{
        "full_name": "ada/compiler",
        "structure_sample": ["src/parser.rs", "tests/parser_test.rs", ".github/workflows/ci.yml"],
        "key_files": [{"path": "src/parser.rs", "content": "fn parse() {}"}],
        "architecture_signals": {"patterns_detected": ["has_tests", "has_ci"], "framework_hints": ["rust"], "file_count": 3, "max_depth": 2},
    }]

    snapshot = build_profile_signal_snapshot(user, [repo], [section], None, payload, generated, code_context)

    assert snapshot["timeline"]["complexity_trend"] == "growing"
    assert "test files present" in snapshot["code_hygiene"]["positive_signals"]
    assert snapshot["architecture"][0]["patterns"] == ["has_tests", "has_ci"]
    assert snapshot["delivery"]["total_commits"] == 80
    assert snapshot["evidence"]["cited_files"] == ["src/parser.rs"]
    assert "Rust compiler project" in snapshot["summary_for_search"]
