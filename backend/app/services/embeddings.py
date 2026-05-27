import logging
from typing import List

from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import CodeChunk

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
    # Allow tests to monkeypatch this function by providing a fake client implementation
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    # Response.data may be list of objects with 'embedding' attribute
    return [getattr(item, "embedding", item.get("embedding") if isinstance(item, dict) else None) for item in response.data]


def embed_repo_files(db: Session, user_id: str, repo_id: str, analysis_id: str, code_context: dict) -> int:
    settings = get_settings()
    if not getattr(settings, "openai_api_key", None):
        return 0

    client = OpenAI(api_key=settings.openai_api_key)
    pending = []

    readme = code_context.get("readme") or ""
    if readme:
        for idx, chunk in enumerate(chunk_text(readme)):
            pending.append(("README.md", idx, chunk))

    for key_file in code_context.get("key_files") or []:
        path = key_file.get("path") or ""
        content = key_file.get("content") or ""
        for idx, chunk in enumerate(chunk_text(content)):
            pending.append((path, idx, chunk))

    if not pending:
        return 0

    stored = 0
    for batch_start in range(0, len(pending), EMBED_BATCH_SIZE):
        batch = pending[batch_start : batch_start + EMBED_BATCH_SIZE]
        try:
            embeddings = embed_batch(client, [content for _, _, content in batch])
        except Exception as exc:
            logger.warning("Embedding batch failed: %s", exc)
            continue
        for (file_path, chunk_index, content), embedding in zip(batch, embeddings, strict=False):
            db.add(CodeChunk(
                user_id=user_id,
                repo_id=repo_id,
                analysis_id=analysis_id,
                file_path=file_path,
                chunk_index=chunk_index,
                content=content,
                embedding=embedding,
            ))
            stored += 1
    db.commit()
    return stored


def embed_query(query: str) -> List[float] | None:
    settings = get_settings()
    if not getattr(settings, "openai_api_key", None):
        return None
    # Allow tests to run without an API key by returning None
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=query)
    first = response.data[0]
    return getattr(first, "embedding", first.get("embedding") if isinstance(first, dict) else None)


def retrieve_chunks(db: Session, user_id: str, analysis_id: str, query: str, top_k: int = 10) -> List[dict]:
    # Only supported for Postgres with pgvector
    if db.bind.dialect.name != "postgresql":
        return []
    query_embedding = embed_query(query)
    if query_embedding is None:
        return []
    stmt = (
        select(CodeChunk)
        .where(CodeChunk.user_id == user_id, CodeChunk.analysis_id == analysis_id)
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


def build_rag_context(db: Session, user_id: str, analysis_id: str, repo_id_to_full_name: dict[str, str], top_k_per_query: int = 8) -> dict:
    dimension_chunks: dict[str, list[dict]] = {}
    seen = set()
    for dimension, query in RAG_DIMENSION_QUERIES.items():
        chunks = retrieve_chunks(db, user_id, analysis_id, query, top_k=top_k_per_query)
        unique = []
        for chunk in chunks:
            key = (chunk["repo_id"], chunk["file_path"], chunk["chunk_index"])
            if key in seen:
                continue
            seen.add(key)
            chunk["repo"] = repo_id_to_full_name.get(chunk["repo_id"], "unknown")
            unique.append(chunk)
        dimension_chunks[dimension] = unique
    return dimension_chunks
