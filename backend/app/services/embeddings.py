import logging
import json
from typing import List

from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import CodeChunk, GeneratedEvaluation, GitHubRepository, ProfileEmbedding, User

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
CHUNK_LINES = 40
CHUNK_OVERLAP = 8
MAX_CHARS_PER_CHUNK = 2400
EMBED_BATCH_SIZE = 100


def chunk_text(content: str, chunk_lines: int = CHUNK_LINES, overlap: int = CHUNK_OVERLAP) -> List[str]:
    if not content:
        return []
    lines = content.splitlines()
    chunks: List[str] = []
    step = max(1, chunk_lines - overlap)
    for start in range(0, len(lines), step):
        chunk = "\n".join(lines[start : start + chunk_lines])
        if len(chunk) > MAX_CHARS_PER_CHUNK:
            chunk = chunk[:MAX_CHARS_PER_CHUNK]
        if chunk.strip():
            chunks.append(chunk)
        if start + chunk_lines >= len(lines):
            break
    return chunks


def embed_batch(client: OpenAI, texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [getattr(item, "embedding", item.get("embedding") if isinstance(item, dict) else None) for item in response.data]


def embed_repo_files(db: Session, user_id: str, repo_id: str, code_context: dict) -> int:
    settings = get_settings()
    if not getattr(settings, "openai_api_key", None):
        return 0

    pending: list[tuple[str, int, str]] = []

    readme = code_context.get("readme") or ""
    if readme:
        for idx, chunk in enumerate(chunk_text(readme)):
            pending.append(("README.md", idx, chunk))

    for key_file in code_context.get("key_files") or []:
        path = key_file.get("path") or ""
        content = key_file.get("content") or ""
        if not path or not content:
            continue
        for idx, chunk in enumerate(chunk_text(content)):
            pending.append((path, idx, chunk))

    if not pending:
        return 0

    db.query(CodeChunk).filter(CodeChunk.user_id == user_id, CodeChunk.repo_id == repo_id).delete(synchronize_session=False)

    client = OpenAI(api_key=settings.openai_api_key)
    stored = 0
    for batch_start in range(0, len(pending), EMBED_BATCH_SIZE):
        batch = pending[batch_start : batch_start + EMBED_BATCH_SIZE]
        try:
            embeddings = embed_batch(client, [content for _, _, content in batch])
        except Exception as exc:
            logger.warning("Embedding batch failed for repo %s: %s", repo_id, exc)
            continue

        for (file_path, chunk_index, content), embedding in zip(batch, embeddings, strict=False):
            if embedding is None:
                continue
            db.add(
                CodeChunk(
                    user_id=user_id,
                    repo_id=repo_id,
                    file_path=file_path,
                    chunk_index=chunk_index,
                    content=content,
                    embedding=embedding,
                )
            )
            stored += 1

    db.commit()
    return stored


def repo_has_embeddings(db: Session, user_id: str, repo_id: str) -> bool:
    return (
        db.query(CodeChunk.id)
        .filter(CodeChunk.user_id == user_id, CodeChunk.repo_id == repo_id)
        .limit(1)
        .first()
        is not None
    )


def embed_query(query: str) -> List[float] | None:
    settings = get_settings()
    if not getattr(settings, "openai_api_key", None):
        return None
    # Allow tests to run without an API key by returning None
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=query)
    first = response.data[0]
    return getattr(first, "embedding", first.get("embedding") if isinstance(first, dict) else None)


def retrieve_chunks(
    db: Session,
    user_id: str,
    query: str,
    top_k: int = 10,
    repo_ids: list[str] | None = None,
) -> List[dict]:
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return []
    if not hasattr(CodeChunk.embedding, "cosine_distance"):
        return []

    query_embedding = embed_query(query)
    if query_embedding is None:
        return []

    filters = [CodeChunk.user_id == user_id]
    if repo_ids:
        filters.append(CodeChunk.repo_id.in_(repo_ids))

    stmt = (
        select(CodeChunk)
        .where(*filters)
        .order_by(CodeChunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )
    results = db.execute(stmt).scalars().all()
    return [
        {
            "file_path": chunk.file_path,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "repo_id": chunk.repo_id,
        }
        for chunk in results
    ]


RAG_DIMENSION_QUERIES = {
    "architecture": "module structure, separation of concerns, dependency injection, layering, interfaces",
    "code_quality": "naming conventions, error handling, readability, edge cases, defensive coding",
    "algorithms": "data structures, algorithms, complexity, optimization, dynamic programming, graph traversal",
    "tests": "test files, assertions, mocks, fixtures, integration tests, coverage",
}


def build_rag_context(
    db: Session,
    user_id: str,
    repo_id_to_full_name: dict[str, str],
    top_k_per_query: int = 16,
) -> dict:
    dimension_chunks: dict[str, list[dict]] = {}
    seen = set()
    repo_ids = list(repo_id_to_full_name)
    for dimension, query in RAG_DIMENSION_QUERIES.items():
        chunks = retrieve_chunks(db, user_id, query, top_k=top_k_per_query * 4, repo_ids=repo_ids)
        unique = []
        per_file_counts: dict[tuple[str, str], int] = {}
        for chunk in chunks:
            key = (chunk["repo_id"], chunk["file_path"], chunk["chunk_index"])
            if key in seen:
                continue
            file_key = (chunk["repo_id"], chunk["file_path"])
            if per_file_counts.get(file_key, 0) >= 2:
                continue
            seen.add(key)
            per_file_counts[file_key] = per_file_counts.get(file_key, 0) + 1
            chunk["repo"] = repo_id_to_full_name.get(chunk["repo_id"], "unknown")
            unique.append(chunk)
            if len(unique) >= top_k_per_query:
                break
        dimension_chunks[dimension] = unique
    return dimension_chunks


def build_profile_search_text(
    user: User,
    evaluation: GeneratedEvaluation,
    repositories: list[GitHubRepository],
) -> str:
    parts: list[str] = []
    if user.name:
        parts.append(user.name)
    if user.headline:
        parts.append(user.headline)

    profile_signal = getattr(evaluation, "profile_signal_snapshot", None)
    if isinstance(profile_signal, dict):
        summary_for_search = profile_signal.get("summary_for_search")
        if summary_for_search:
            parts.append(str(summary_for_search))
        parts.append("Developer profile signal:")
        parts.append(json.dumps(profile_signal, ensure_ascii=False, sort_keys=True))

    if evaluation.summary:
        parts.append(evaluation.summary)

    skill_model = evaluation.skill_model_v2 if isinstance(evaluation.skill_model_v2, dict) else {}
    for dimension in ("code_quality", "delivery", "algorithms"):
        prose = (skill_model.get(dimension) or {}).get("prose")
        if prose:
            parts.append(prose)

    strengths = evaluation.strengths if isinstance(evaluation.strengths, list) else []
    parts.extend(str(s) for s in strengths if s)

    languages = sorted({repo.language for repo in repositories if repo.language})
    if languages:
        parts.append("Languages: " + ", ".join(languages))

    repo_names = [repo.full_name for repo in repositories if repo.full_name][:20]
    if repo_names:
        parts.append("Repositories: " + ", ".join(repo_names))

    return "\n".join(parts).strip()


def upsert_profile_embedding(
    db: Session,
    user: User,
    evaluation: GeneratedEvaluation,
    repositories: list[GitHubRepository],
) -> ProfileEmbedding | None:
    source_text = build_profile_search_text(user, evaluation, repositories)
    if not source_text:
        return None

    embedding = embed_query(source_text)
    if embedding is None:
        return None

    record = db.get(ProfileEmbedding, user.id)
    if record is None:
        record = ProfileEmbedding(user_id=user.id)
        db.add(record)
    record.source_text = source_text
    record.embedding = embedding
    record.summary = evaluation.summary
    db.commit()
    db.refresh(record)
    return record


def search_profiles(
    db: Session,
    query: str,
    limit: int = 10,
    published_only: bool = True,
) -> list[dict]:
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return []
    if not hasattr(ProfileEmbedding.embedding, "cosine_distance"):
        return []

    query_embedding = embed_query(query)
    if query_embedding is None:
        return []

    distance = ProfileEmbedding.embedding.cosine_distance(query_embedding)
    stmt = (
        select(ProfileEmbedding, User, distance.label("distance"))
        .join(User, User.id == ProfileEmbedding.user_id)
        .order_by(distance)
        .limit(limit)
    )
    if published_only:
        stmt = stmt.where(User.published.is_(True))
    results = db.execute(stmt).all()
    return [
        {
            "user_id": user.id,
            "slug": user.slug,
            "name": user.name,
            "headline": user.headline,
            "summary": profile.summary,
            "score": float(1.0 - dist) if dist is not None else None,
        }
        for profile, user, dist in results
    ]
