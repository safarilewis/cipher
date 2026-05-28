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
    from app.services.embeddings import embed_repo_files

    user = User(id="u1", slug="ada")
    repo = GitHubRepository(id="r1", user_id="u1", full_name="ada/app")
    db_session.add_all([user, repo])
    db_session.commit()

    class Settings:
        openai_api_key = "test-key"

    class FakeOpenAI:
        def __init__(self, api_key):
            assert api_key == "test-key"

    monkeypatch.setattr("app.services.embeddings.get_settings", lambda: Settings())
    monkeypatch.setattr("app.services.embeddings.OpenAI", FakeOpenAI)
    monkeypatch.setattr("app.services.embeddings.embed_batch", lambda client, texts: [[0.1] * 1536 for _ in texts])

    stored = embed_repo_files(
        db=db_session,
        user_id="u1",
        repo_id="r1",
        code_context={
            "readme": "hello\nworld",
            "key_files": [{"path": "app/main.py", "content": "def main():\n    return True"}],
        },
    )

    chunks = db_session.query(CodeChunk).filter(CodeChunk.repo_id == "r1").all()
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
