import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.services.embeddings import chunk_text


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_chunk_text_empty():
    assert chunk_text("") == []


def test_chunk_text_short_content():
    chunks = chunk_text("line1\nline2\nline3")
    assert len(chunks) == 1


def test_chunk_text_long_content_with_overlap():
    content = "\n".join(f"line{i}" for i in range(100))
    chunks = chunk_text(content, chunk_lines=20, overlap=4)
    assert len(chunks) > 1


def test_chunk_text_respects_max_chars():
    long_line = "x" * 10000
    chunks = chunk_text(long_line, chunk_lines=1)
    assert all(len(c) <= 2400 for c in chunks)


def test_retrieve_chunks_returns_empty_for_sqlite(db_session):
    from app.services.embeddings import retrieve_chunks

    assert retrieve_chunks(db_session, user_id="u1", query="architecture") == []


def test_embed_repo_files_stores_chunks_with_mocked_embeddings(db_session, monkeypatch):
    from app.models import CodeChunk, GitHubRepository, User
    from app.services.embeddings import embed_repo_files, embed_repo_files_report

    user = User(id="u1", slug="ada")
    repo = GitHubRepository(id="r1", user_id="u1", full_name="ada/app")
    db_session.add_all([user, repo])
    db_session.commit()

    class Settings:
        voyage_api_key = "test-key"
        voyage_embedding_model = "voyage-2"

    class FakeVoyageClient:
        def __init__(self, api_key):
            assert api_key == "test-key"

    monkeypatch.setattr("app.services.embeddings.get_settings", lambda: Settings())
    monkeypatch.setattr("app.services.embeddings.create_voyage_client", FakeVoyageClient)
    monkeypatch.setattr("app.services.embeddings.embed_batch", lambda client, texts, **kwargs: [[0.1] * 1024 for _ in texts])

    code_context = {
        "readme": "hello\nworld",
        "key_files": [{"path": "app/main.py", "content": "def main():\n    return True"}],
    }
    report = embed_repo_files_report(
        db=db_session,
        user_id="u1",
        repo_id="r1",
        code_context=code_context,
    )
    stored = embed_repo_files(db=db_session, user_id="u1", repo_id="r1", code_context=code_context)

    chunks = db_session.query(CodeChunk).filter(CodeChunk.repo_id == "r1").all()
    assert report == {"chunks_pending": 2, "chunks_stored": 2, "errors": []}
    assert stored == 2
    assert {chunk.file_path for chunk in chunks} == {"README.md", "app/main.py"}


def test_build_rag_context_diversifies_files(monkeypatch, db_session):
    from app.services.embeddings import build_rag_context

    chunks = [
        {"repo_id": "r1", "file_path": "src/a.py", "chunk_index": 0, "content": "a0"},
        {"repo_id": "r1", "file_path": "src/a.py", "chunk_index": 1, "content": "a1"},
        {"repo_id": "r1", "file_path": "src/a.py", "chunk_index": 2, "content": "a2"},
        {"repo_id": "r1", "file_path": "src/b.py", "chunk_index": 0, "content": "b0"},
        {"repo_id": "r1", "file_path": "src/c.py", "chunk_index": 0, "content": "c0"},
    ]

    monkeypatch.setattr("app.services.embeddings.retrieve_chunks", lambda *args, **kwargs: chunks)

    rag_context = build_rag_context(db_session, "u1", {"r1": "ada/app"}, top_k_per_query=4)
    architecture = rag_context["architecture"]

    assert [chunk["file_path"] for chunk in architecture] == ["src/a.py", "src/a.py", "src/b.py", "src/c.py"]
    assert all(chunk["repo"] == "ada/app" for chunk in architecture)


def test_build_rag_context_limits_readme_dominance(monkeypatch, db_session):
    from app.services.embeddings import build_rag_context

    chunks = [
        {"repo_id": "r1", "file_path": "README.md", "chunk_index": 0, "content": "readme0"},
        {"repo_id": "r1", "file_path": "README.md", "chunk_index": 1, "content": "readme1"},
        {"repo_id": "r1", "file_path": "src/service.py", "chunk_index": 0, "content": "service"},
        {"repo_id": "r1", "file_path": "tests/test_service.py", "chunk_index": 0, "content": "tests"},
    ]

    monkeypatch.setattr("app.services.embeddings.retrieve_chunks", lambda *args, **kwargs: chunks)

    rag_context = build_rag_context(db_session, "u1", {"r1": "ada/app"}, top_k_per_query=3)
    architecture = rag_context["architecture"]

    assert [chunk["file_path"] for chunk in architecture] == ["README.md", "src/service.py", "tests/test_service.py"]


def test_build_profile_search_text_assembles_query_friendly_blob():
    from types import SimpleNamespace
    from app.services.embeddings import build_profile_search_text

    user = SimpleNamespace(name="Ada", headline="Compiler builder")
    evaluation = SimpleNamespace(
        summary="Built a parser in Rust over two semesters.",
        profile_signal_snapshot={
            "summary_for_search": "Live profile: Rust compiler, improving tests, active commits.",
            "code_hygiene": {"positive_signals": ["test files present"]},
        },
        skill_model_v2={
            "code_quality": {"prose": "Clean Rust idioms, ownership respected."},
            "delivery": {"prose": "Ships in spurts."},
            "algorithms": {"prose": "Parser/lexer DSA only."},
        },
        strengths=["Strong systems instincts", "Test discipline"],
    )
    repos = [
        SimpleNamespace(full_name="ada/parser", language="Rust"),
        SimpleNamespace(full_name="ada/runtime", language="Rust"),
        SimpleNamespace(full_name="ada/tools", language="Python"),
    ]

    text = build_profile_search_text(user, evaluation, repos)

    assert "Ada" in text
    assert "Compiler builder" in text
    assert "Live profile: Rust compiler" in text
    assert "test files present" in text
    assert "Built a parser" in text
    assert "Clean Rust idioms" in text
    assert "Strong systems instincts" in text
    assert "Languages: Python, Rust" in text
    assert "ada/parser" in text


def test_upsert_profile_embedding_writes_record(db_session, monkeypatch):
    from types import SimpleNamespace
    from app.models import ProfileEmbedding, User
    from app.services.embeddings import upsert_profile_embedding

    user = User(id="u-search", slug="ada", name="Ada", headline="Hacker")
    db_session.add(user)
    db_session.commit()

    evaluation = SimpleNamespace(
        summary="Hacker summary.",
        profile_signal_snapshot={"summary_for_search": "Queryable hacker profile."},
        skill_model_v2={"code_quality": {"prose": "tidy"}},
        strengths=["focus"],
    )
    monkeypatch.setattr("app.services.embeddings.embed_query", lambda text: [0.1] * 1024)

    record = upsert_profile_embedding(db_session, user, evaluation, repositories=[])

    assert record is not None
    stored = db_session.get(ProfileEmbedding, "u-search")
    assert stored.summary == "Hacker summary."
    assert "Queryable hacker profile." in stored.source_text
    assert "Hacker summary." in stored.source_text


def test_search_profiles_returns_empty_on_sqlite(db_session):
    from app.services.embeddings import search_profiles

    assert search_profiles(db_session, query="rust compilers") == []
