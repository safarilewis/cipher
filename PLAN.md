# adpt — RAG Code Analysis Implementation Plan

# For GitHub Copilot

# Backend: Python

# Vector store: pgvector (existing Postgres, no new infrastructure)

-----

## Objective

Replace the current full-file code context stuffing with a RAG retrieval layer.
Index repo code at sync time. Retrieve targeted chunks at analysis time.
Result: faster evaluations, better signal, lower token usage.

-----

## Constraints

- Use pgvector on existing Postgres. Do NOT introduce Chroma or any external
  vector store. One `CREATE EXTENSION IF NOT EXISTS vector;` is all that’s needed.
- Chunk by semantic boundary (function/class/module), NOT by fixed token count.
  A complete 80-token function is better signal than a random 512-token slice.
- Index once at sync time, query many times at analysis time.
- All vector store access must go through a thin abstract interface so the
  implementation can be swapped without touching analysis logic.

-----

## 1. DATABASE MIGRATION

Create this migration file: `migrations/add_code_chunks.sql`

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Code chunks table
CREATE TABLE IF NOT EXISTS code_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    repo_full_name  TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    chunk_index     INTEGER NOT NULL,
    content         TEXT NOT NULL,
    embedding       vector(1536),
    token_count     INTEGER,
    chunk_type      TEXT CHECK (chunk_type IN (
                        'function', 'class', 'module',
                        'config', 'test', 'other'
                    )),
    language        TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, repo_full_name, file_path, chunk_index)
);

-- IVFFlat index for cosine similarity search
-- lists = sqrt(expected row count). Start with 100, tune later.
CREATE INDEX IF NOT EXISTS code_chunks_embedding_idx
    ON code_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Fast lookup by user + repo (for deletion on re-sync)
CREATE INDEX IF NOT EXISTS code_chunks_user_repo_idx
    ON code_chunks (user_id, repo_full_name);
```

Run this migration before any other changes.

-----

## 2. CONFIG

Add to `config.py`:

```python
# Embedding model
EMBEDDING_MODEL: str = "text-embedding-3-small"  # 1536 dimensions, cheap, fast
EMBEDDING_BATCH_SIZE: int = 20                    # chunks per embedding API call

# Retrieval settings
RAG_TOP_K_PER_QUERY: int = 3       # chunks returned per signal query
RAG_MAX_CHUNK_TOKENS: int = 400    # hard cap per chunk before embedding
RAG_MAX_TOTAL_TOKENS: int = 6000   # hard cap on total RAG content in prompt

# Files to never index
RAG_EXCLUDED_PATTERNS: list[str] = [
    "package-lock.json",
    "yarn.lock",
    "poetry.lock",
    "*.min.js",
    "*.min.css",
    "dist/",
    "build/",
    ".next/",
    "__pycache__/",
    "*.pyc",
    "node_modules/",
    ".env",
    "*.lock",
]

# Files to always index (high signal, fetch first)
RAG_PRIORITY_FILES: list[str] = [
    "README.md",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "Dockerfile",
    "src/index.ts",
    "src/main.ts",
    "src/App.tsx",
    "app/main.py",
    "main.py",
    "index.py",
]
```

-----

## 3. ABSTRACT VECTOR STORE INTERFACE

Create `backend/app/services/vector_store.py`:

```python
from __future__ import annotations
from typing import Protocol, runtime_checkable
from dataclasses import dataclass


@dataclass
class CodeChunk:
    user_id: str
    repo_full_name: str
    file_path: str
    chunk_index: int
    content: str
    chunk_type: str        # 'function' | 'class' | 'module' | 'config' | 'test' | 'other'
    language: str | None
    token_count: int
    embedding: list[float] | None = None


@runtime_checkable
class VectorStore(Protocol):
    """
    Abstract interface for vector store operations.
    All RAG logic must use this interface — never call pgvector directly
    from analysis or github services.
    """

    def upsert_chunks(self, chunks: list[CodeChunk]) -> None:
        """Insert or update chunks. Uses (user_id, repo, file_path, chunk_index) as key."""
        ...

    def query(
        self,
        user_id: str,
        repo_full_name: str,
        query_embedding: list[float],
        top_k: int,
    ) -> list[CodeChunk]:
        """Return top_k most similar chunks for this user+repo."""
        ...

    def delete_repo(self, user_id: str, repo_full_name: str) -> None:
        """Delete all chunks for a repo. Call before re-indexing."""
        ...

    def delete_user(self, user_id: str) -> None:
        """Delete all chunks for a user. Call on account deletion."""
        ...
```

-----

## 4. PGVECTOR IMPLEMENTATION

Create `backend/app/services/pgvector_store.py`:

```python
from __future__ import annotations
import logging
from typing import Any
from .vector_store import CodeChunk, VectorStore

logger = logging.getLogger(__name__)


class PgVectorStore:
    """
    pgvector implementation of VectorStore.
    Inject a db connection/pool — do not manage connections internally.
    """

    def __init__(self, db: Any):
        # db should be your existing asyncpg pool or psycopg2 connection
        # Match whatever pattern the rest of the codebase uses
        self.db = db

    def upsert_chunks(self, chunks: list[CodeChunk]) -> None:
        if not chunks:
            return

        rows = [
            (
                c.user_id,
                c.repo_full_name,
                c.file_path,
                c.chunk_index,
                c.content,
                c.chunk_type,
                c.language,
                c.token_count,
                c.embedding,  # list[float] — pgvector accepts Python lists
            )
            for c in chunks
            if c.embedding is not None
        ]

        # Adapt this to your DB access pattern (asyncpg / psycopg2 / SQLAlchemy)
        self.db.executemany(
            """
            INSERT INTO code_chunks
                (user_id, repo_full_name, file_path, chunk_index,
                 content, chunk_type, language, token_count, embedding)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (user_id, repo_full_name, file_path, chunk_index)
            DO UPDATE SET
                content     = EXCLUDED.content,
                chunk_type  = EXCLUDED.chunk_type,
                token_count = EXCLUDED.token_count,
                embedding   = EXCLUDED.embedding,
                created_at  = NOW()
            """,
            rows,
        )
        logger.info(f"Upserted {len(rows)} chunks")

    def query(
        self,
        user_id: str,
        repo_full_name: str,
        query_embedding: list[float],
        top_k: int,
    ) -> list[CodeChunk]:
        rows = self.db.execute(
            """
            SELECT
                user_id, repo_full_name, file_path, chunk_index,
                content, chunk_type, language, token_count
            FROM code_chunks
            WHERE user_id = $1
              AND repo_full_name = $2
              AND embedding IS NOT NULL
            ORDER BY embedding <=> $3   -- cosine distance
            LIMIT $4
            """,
            user_id,
            repo_full_name,
            query_embedding,
            top_k,
        )
        return [
            CodeChunk(
                user_id=r["user_id"],
                repo_full_name=r["repo_full_name"],
                file_path=r["file_path"],
                chunk_index=r["chunk_index"],
                content=r["content"],
                chunk_type=r["chunk_type"],
                language=r["language"],
                token_count=r["token_count"],
            )
            for r in rows
        ]

    def delete_repo(self, user_id: str, repo_full_name: str) -> None:
        self.db.execute(
            "DELETE FROM code_chunks WHERE user_id = $1 AND repo_full_name = $2",
            user_id,
            repo_full_name,
        )
        logger.info(f"Deleted chunks for {repo_full_name}")

    def delete_user(self, user_id: str) -> None:
        self.db.execute(
            "DELETE FROM code_chunks WHERE user_id = $1",
            user_id,
        )
```

-----

## 5. CHUNKER

Create `backend/app/services/chunker.py`:

```python
from __future__ import annotations
import re
import logging
from .vector_store import CodeChunk
from config import RAG_MAX_CHUNK_TOKENS

logger = logging.getLogger(__name__)

# Rough token estimator (4 chars ≈ 1 token)
def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _truncate_to_token_limit(text: str, limit: int = RAG_MAX_CHUNK_TOKENS) -> str:
    if _estimate_tokens(text) <= limit:
        return text
    # Truncate by character approximation
    return text[: limit * 4]


def chunk_file(
    content: str,
    file_path: str,
    user_id: str,
    repo_full_name: str,
    language: str | None,
) -> list[CodeChunk]:
    """
    Chunk a file by semantic boundary.
    Priority: function/class definitions > module-level blocks > sliding window fallback.
    Never chunk by fixed token count alone.
    """
    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""

    if ext in ("ts", "tsx", "js", "jsx"):
        raw_chunks = _chunk_typescript(content)
    elif ext == "py":
        raw_chunks = _chunk_python(content)
    elif ext in ("json", "toml", "yaml", "yml", "dockerfile", "env"):
        raw_chunks = _chunk_config(content, file_path)
    elif "test" in file_path.lower() or "spec" in file_path.lower():
        raw_chunks = _chunk_tests(content, ext)
    else:
        raw_chunks = _chunk_sliding_window(content)

    chunks = []
    for i, (chunk_type, text) in enumerate(raw_chunks):
        text = text.strip()
        if not text:
            continue
        text = _truncate_to_token_limit(text)
        chunks.append(
            CodeChunk(
                user_id=user_id,
                repo_full_name=repo_full_name,
                file_path=file_path,
                chunk_index=i,
                content=text,
                chunk_type=chunk_type,
                language=language or ext or "unknown",
                token_count=_estimate_tokens(text),
            )
        )

    return chunks


def _chunk_python(content: str) -> list[tuple[str, str]]:
    """Split on top-level def and class boundaries."""
    pattern = re.compile(r"^(class |def )", re.MULTILINE)
    boundaries = [m.start() for m in pattern.finditer(content)]

    if not boundaries:
        return [("module", content)]

    chunks = []
    # Content before first definition
    if boundaries[0] > 0:
        chunks.append(("module", content[: boundaries[0]]))

    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(content)
        block = content[start:end]
        chunk_type = "class" if block.startswith("class ") else "function"
        chunks.append((chunk_type, block))

    return chunks


def _chunk_typescript(content: str) -> list[tuple[str, str]]:
    """Split on function, class, and export boundaries."""
    pattern = re.compile(
        r"^(export\s+)?(default\s+)?(async\s+)?(function|class|const\s+\w+\s*=\s*(async\s*)?\()",
        re.MULTILINE,
    )
    boundaries = [m.start() for m in pattern.finditer(content)]

    if not boundaries:
        return [("module", content)]

    chunks = []
    if boundaries[0] > 0:
        chunks.append(("module", content[: boundaries[0]]))

    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(content)
        block = content[start:end]
        chunk_type = "class" if "class " in block[:50] else "function"
        chunks.append((chunk_type, block))

    return chunks


def _chunk_config(content: str, file_path: str) -> list[tuple[str, str]]:
    """Config files as single chunks if under token limit, else skip."""
    if _estimate_tokens(content) <= RAG_MAX_CHUNK_TOKENS:
        return [("config", content)]
    # Too large — take first RAG_MAX_CHUNK_TOKENS worth (most important part)
    return [("config", _truncate_to_token_limit(content))]


def _chunk_tests(content: str, ext: str) -> list[tuple[str, str]]:
    """Split test files on describe/it/test block boundaries."""
    if ext == "py":
        pattern = re.compile(r"^(class Test|def test_)", re.MULTILINE)
    else:
        pattern = re.compile(r"^(describe\(|it\(|test\()", re.MULTILINE)

    boundaries = [m.start() for m in pattern.finditer(content)]

    if not boundaries:
        return [("test", content)]

    chunks = []
    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(content)
        chunks.append(("test", content[start:end]))

    return chunks


def _chunk_sliding_window(
    content: str,
    window_lines: int = 40,
    overlap_lines: int = 8,
) -> list[tuple[str, str]]:
    """Fallback: sliding window over lines with overlap."""
    lines = content.splitlines()
    if len(lines) <= window_lines:
        return [("other", content)]

    chunks = []
    step = window_lines - overlap_lines
    for i in range(0, len(lines), step):
        block = "\n".join(lines[i : i + window_lines])
        chunks.append(("other", block))

    return chunks
```

-----

## 6. RETRIEVER SERVICE

Create `backend/app/services/retriever.py`:

```python
from __future__ import annotations
import logging
from openai import OpenAI
from .vector_store import VectorStore, CodeChunk
from .chunker import chunk_file
from config import (
    EMBEDDING_MODEL,
    EMBEDDING_BATCH_SIZE,
    RAG_TOP_K_PER_QUERY,
    RAG_MAX_TOTAL_TOKENS,
    RAG_EXCLUDED_PATTERNS,
)

logger = logging.getLogger(__name__)

# These queries target the exact signal dimensions the evaluator needs.
# Each query retrieves different evidence. Do not reduce this list.
SIGNAL_QUERIES = [
    "main application entry point and initialization logic",
    "data models type definitions and schema",
    "core business logic and domain algorithms",
    "API routes controllers and request handling",
    "test files testing patterns and assertions",
    "database queries data access and persistence layer",
]


def _should_exclude(file_path: str) -> bool:
    from config import RAG_EXCLUDED_PATTERNS
    for pattern in RAG_EXCLUDED_PATTERNS:
        if pattern.endswith("/"):
            if pattern.rstrip("/") in file_path:
                return True
        elif pattern.startswith("*"):
            if file_path.endswith(pattern[1:]):
                return True
        elif file_path.endswith(pattern) or pattern in file_path:
            return True
    return False


def _embed_texts(client: OpenAI, texts: list[str]) -> list[list[float]]:
    """Embed a list of texts in batches. Returns embeddings in same order."""
    all_embeddings = []
    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i : i + EMBEDDING_BATCH_SIZE]
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=batch,
        )
        all_embeddings.extend([r.embedding for r in response.data])
    return all_embeddings


def index_repository(
    *,
    user_id: str,
    repo_full_name: str,
    code_context: dict,          # RepositoryCodeContext shape from github.py
    vector_store: VectorStore,
    openai_client: OpenAI,
) -> int:
    """
    Index a single repository's code context into the vector store.
    Call this after fetching repo code context during GitHub sync.
    Returns number of chunks indexed.
    """
    # Clear existing chunks for this repo before re-indexing
    vector_store.delete_repo(user_id, repo_full_name)

    language = code_context.get("language")
    all_chunks: list[CodeChunk] = []

    # Index key files
    for key_file in code_context.get("key_files", []):
        path = key_file.get("path", "")
        content = key_file.get("content", "")

        if not content or not path:
            continue

        if _should_exclude(path):
            logger.debug(f"Skipping excluded file: {path}")
            continue

        file_chunks = chunk_file(
            content=content,
            file_path=path,
            user_id=user_id,
            repo_full_name=repo_full_name,
            language=language,
        )
        all_chunks.extend(file_chunks)

    # Index README as a single chunk (already truncated by github.py)
    readme = code_context.get("readme", "")
    if readme:
        all_chunks.append(
            CodeChunk(
                user_id=user_id,
                repo_full_name=repo_full_name,
                file_path="README.md",
                chunk_index=0,
                content=readme,
                chunk_type="other",
                language=None,
                token_count=max(1, len(readme) // 4),
            )
        )

    if not all_chunks:
        logger.warning(f"No indexable content found for {repo_full_name}")
        return 0

    # Embed all chunks
    texts = [c.content for c in all_chunks]
    try:
        embeddings = _embed_texts(openai_client, texts)
    except Exception as e:
        logger.error(f"Embedding failed for {repo_full_name}: {e}")
        raise

    for chunk, embedding in zip(all_chunks, embeddings):
        chunk.embedding = embedding

    vector_store.upsert_chunks(all_chunks)
    logger.info(f"Indexed {len(all_chunks)} chunks for {repo_full_name}")
    return len(all_chunks)


def retrieve_evidence(
    *,
    user_id: str,
    repo_full_name: str,
    vector_store: VectorStore,
    openai_client: OpenAI,
) -> list[dict]:
    """
    Run all signal queries against a repo's indexed chunks.
    Returns deduplicated top-k chunks across all queries,
    formatted for inclusion in the evaluation prompt.
    Hard-capped at RAG_MAX_TOTAL_TOKENS total.
    """
    # Embed all signal queries in one batch
    query_embeddings = _embed_texts(openai_client, SIGNAL_QUERIES)

    seen_keys: set[tuple[str, int]] = set()
    results: list[CodeChunk] = []

    for query, q_embedding in zip(SIGNAL_QUERIES, query_embeddings):
        chunks = vector_store.query(
            user_id=user_id,
            repo_full_name=repo_full_name,
            query_embedding=q_embedding,
            top_k=RAG_TOP_K_PER_QUERY,
        )
        for chunk in chunks:
            key = (chunk.file_path, chunk.chunk_index)
            if key not in seen_keys:
                seen_keys.add(key)
                results.append(chunk)

    # Enforce total token cap
    capped: list[CodeChunk] = []
    total_tokens = 0
    for chunk in results:
        if total_tokens + chunk.token_count > RAG_MAX_TOTAL_TOKENS:
            break
        capped.append(chunk)
        total_tokens += chunk.token_count

    logger.info(
        f"Retrieved {len(capped)} chunks ({total_tokens} tokens) for {repo_full_name}"
    )

    # Format for prompt inclusion
    return [
        {
            "file_path": c.file_path,
            "chunk_type": c.chunk_type,
            "content": c.content,
        }
        for c in capped
    ]
```

-----

## 7. WIRE INTO GITHUB SYNC

In `github.py`, after fetching repository code context, trigger indexing:

```python
# After existing code context fetch logic, add:

from .retriever import index_repository
from .pgvector_store import PgVectorStore
from openai import OpenAI

def fetch_and_index_repo_context(
    user_id: str,
    repo: GitHubRepository,
    db,
    openai_client: OpenAI,
) -> RepositoryCodeContext:
    # ... existing fetch logic ...
    code_context = fetch_repo_code_context(repo)  # existing function

    # Index in background — do not block the sync response
    # If you have BullMQ/background jobs wired, enqueue instead of calling directly
    try:
        vector_store = PgVectorStore(db)
        index_repository(
            user_id=user_id,
            repo_full_name=repo.full_name,
            code_context=code_context,
            vector_store=vector_store,
            openai_client=openai_client,
        )
    except Exception as e:
        # Indexing failure must never break the sync
        logger.error(f"RAG indexing failed for {repo.full_name}: {e}")

    return code_context
```

-----

## 8. WIRE INTO ANALYSIS

In `analysis.py`, in `run_analysis()`, replace the raw code context stuffing
with RAG retrieval:

```python
from .retriever import retrieve_evidence
from .pgvector_store import PgVectorStore

def run_analysis(user_id: str, db, openai_client: OpenAI) -> EvaluationOutput:
    # ... existing payload building ...

    vector_store = PgVectorStore(db)

    # Replace: selected_repository_code_context (raw files)
    # With:    retrieved evidence per repo
    rag_evidence: dict[str, list[dict]] = {}

    for repo in payload.selected_repositories_for_code_review:
        evidence = retrieve_evidence(
            user_id=user_id,
            repo_full_name=repo.full_name,
            vector_store=vector_store,
            openai_client=openai_client,
        )
        if evidence:
            rag_evidence[repo.full_name] = evidence
        else:
            # Fall back to existing code context if RAG index not ready
            logger.warning(
                f"RAG index not ready for {repo.full_name}, falling back to raw context"
            )

    # Attach to payload
    payload.rag_evidence = rag_evidence

    # Pass to generate_with_openai as before
    return generate_with_openai(payload, openai_client)
```

-----

## 9. UPDATE PROMPT

In `EVALUATION_INSTRUCTIONS`, add this block before the existing code review section:

```
RETRIEVED CODE EVIDENCE
The following sections contain targeted code snippets retrieved via semantic
search from the developer's repositories. Each snippet is labeled with its
file path and chunk type.

These snippets were selected to answer specific questions about:
- Application architecture and entry points
- Data models and type definitions
- Core business logic
- API and request handling patterns
- Test coverage and patterns
- Data access layer

Evaluate based on these retrieved snippets. Do not assume content exists
that is not shown. If a dimension (e.g. tests) has no retrieved evidence,
note that no test signal was found — do not invent it.

Format in prompt:
[repo: {repo_full_name}]
[file: {file_path} | type: {chunk_type}]
{content}
---
```

Add a formatting helper in `build_evaluation_input()`:

```python
def format_rag_evidence(rag_evidence: dict[str, list[dict]]) -> str:
    if not rag_evidence:
        return "No code evidence retrieved. Evaluate from repository metadata only."

    lines = []
    for repo_name, chunks in rag_evidence.items():
        lines.append(f"[repo: {repo_name}]")
        for chunk in chunks:
            lines.append(f"[file: {chunk['file_path']} | type: {chunk['chunk_type']}]")
            lines.append(chunk["content"])
            lines.append("---")
    return "\n".join(lines)
```

-----

## 10. BACKGROUND JOB

Add to `jobs.py`:

```python
def enqueue_repo_indexing(user_id: str, repo_full_name: str) -> None:
    """
    Enqueue a background job to (re)index a repository.
    Call this from github.py instead of indexing synchronously.
    """
    # Use your existing BullMQ/job queue pattern
    queue.add("index_repo", {
        "user_id": user_id,
        "repo_full_name": repo_full_name,
    })


def process_index_repo_job(job_data: dict) -> None:
    """Job processor — wire this into your existing job runner."""
    user_id = job_data["user_id"]
    repo_full_name = job_data["repo_full_name"]

    # Fetch stored code context from DB (already stored by github.py)
    code_context = get_stored_code_context(user_id, repo_full_name)
    if not code_context:
        logger.warning(f"No code context found for {repo_full_name}, skipping indexing")
        return

    vector_store = PgVectorStore(get_db())
    openai_client = OpenAI()

    index_repository(
        user_id=user_id,
        repo_full_name=repo_full_name,
        code_context=code_context,
        vector_store=vector_store,
        openai_client=openai_client,
    )
```

-----

## 11. ADMIN ENDPOINT

Add to API routes:

```python
@router.post("/admin/reindex/{user_id}")
def reindex_user_repos(user_id: str, db=Depends(get_db)):
    """
    Trigger re-indexing of all selected repos for a user.
    Use after schema changes or prompt updates that require fresh embeddings.
    """
    repos = get_selected_repos_for_user(user_id, db)
    for repo in repos:
        enqueue_repo_indexing(user_id, repo.full_name)
    return {"enqueued": len(repos)}


@router.delete("/admin/index/{user_id}")
def clear_user_index(user_id: str, db=Depends(get_db)):
    """Clear all code chunks for a user. Use before full re-sync."""
    vector_store = PgVectorStore(db)
    vector_store.delete_user(user_id)
    return {"deleted": True}
```

-----

## 12. TESTS

Create `backend/tests/test_retriever.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
from app.services.retriever import index_repository, retrieve_evidence
from app.services.chunker import chunk_file
from app.services.vector_store import CodeChunk


# ── Chunker tests ──────────────────────────────────────────────────────────────

def test_chunk_python_splits_on_functions():
    content = "import os\n\ndef foo():\n    return 1\n\ndef bar():\n    return 2\n"
    chunks = chunk_file(content, "main.py", "user1", "repo/x", "python")
    types = [c.chunk_type for c in chunks]
    assert "function" in types
    assert all(c.content for c in chunks)


def test_chunk_typescript_splits_on_functions():
    content = "const x = 1;\n\nfunction foo() {\n  return 1;\n}\n\nclass Bar {\n  method() {}\n}\n"
    chunks = chunk_file(content, "index.ts", "user1", "repo/x", "typescript")
    assert len(chunks) >= 2


def test_chunk_respects_token_limit():
    long_content = "x = 1\n" * 1000
    chunks = chunk_file(long_content, "main.py", "user1", "repo/x", "python")
    for chunk in chunks:
        assert chunk.token_count <= 400 + 10  # small tolerance


def test_excluded_files_not_chunked():
    from app.services.retriever import _should_exclude
    assert _should_exclude("package-lock.json") is True
    assert _should_exclude("dist/bundle.js") is True
    assert _should_exclude("src/index.ts") is False


# ── Retriever tests ────────────────────────────────────────────────────────────

def test_index_repository_calls_upsert(mock_vector_store, mock_openai):
    code_context = {
        "language": "TypeScript",
        "readme": "A test repo",
        "key_files": [
            {"path": "src/index.ts", "content": "function main() { return 1; }"}
        ],
    }

    count = index_repository(
        user_id="user1",
        repo_full_name="user/repo",
        code_context=code_context,
        vector_store=mock_vector_store,
        openai_client=mock_openai,
    )

    assert count > 0
    assert mock_vector_store.upsert_chunks.called
    assert mock_vector_store.delete_repo.called


def test_retrieve_evidence_deduplicates(mock_vector_store, mock_openai):
    # Same chunk returned by multiple queries should appear once
    chunk = CodeChunk(
        user_id="user1", repo_full_name="user/repo",
        file_path="src/index.ts", chunk_index=0,
        content="function main() {}", chunk_type="function",
        language="typescript", token_count=10,
    )
    mock_vector_store.query.return_value = [chunk]

    results = retrieve_evidence(
        user_id="user1",
        repo_full_name="user/repo",
        vector_store=mock_vector_store,
        openai_client=mock_openai,
    )

    file_paths = [r["file_path"] for r in results]
    assert file_paths.count("src/index.ts") == 1


def test_retrieve_evidence_respects_token_cap(mock_vector_store, mock_openai):
    # Return chunks that would exceed token cap
    big_chunk = CodeChunk(
        user_id="user1", repo_full_name="user/repo",
        file_path=f"file.ts", chunk_index=0,
        content="x" * 2000, chunk_type="function",
        language="typescript", token_count=500,
    )
    mock_vector_store.query.return_value = [big_chunk] * 20

    results = retrieve_evidence(
        user_id="user1",
        repo_full_name="user/repo",
        vector_store=mock_vector_store,
        openai_client=mock_openai,
    )

    total_tokens = sum(len(r["content"]) // 4 for r in results)
    assert total_tokens <= 6000 + 500  # cap + one chunk tolerance


# ── Integration: analysis uses RAG evidence ────────────────────────────────────

def test_run_analysis_includes_rag_evidence():
    """
    Verify run_analysis attaches RAG evidence to the payload
    before calling generate_with_openai.
    """
    with patch("app.services.analysis.retrieve_evidence") as mock_retrieve, \
         patch("app.services.analysis.generate_with_openai") as mock_generate:

        mock_retrieve.return_value = [
            {"file_path": "src/index.ts", "chunk_type": "function", "content": "function main() {}"}
        ]
        mock_generate.return_value = {}  # don't care about output shape here

        from app.services.analysis import run_analysis
        run_analysis(user_id="user1", db=MagicMock(), openai_client=MagicMock())

        assert mock_retrieve.called
        call_args = mock_generate.call_args
        payload = call_args[0][0]
        assert hasattr(payload, "rag_evidence")
        assert len(payload.rag_evidence) > 0


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_vector_store():
    store = MagicMock()
    store.query.return_value = []
    return store


@pytest.fixture
def mock_openai():
    client = MagicMock()
    client.embeddings.create.return_value = MagicMock(
        data=[MagicMock(embedding=[0.1] * 1536)]
    )
    return client
```

-----

## 13. DEPENDENCIES

Add to `pyproject.toml`:

```toml
[tool.poetry.dependencies]
pgvector = ">=0.2.0"    # pgvector Python client
openai = ">=1.0.0"      # already present, ensure >=1.0.0 for new embeddings API
```

Do NOT add chromadb. pgvector is the only vector store.

-----

## 14. IMPLEMENTATION CHECKLIST

Implement in this exact order:

- [ ] Run `migrations/add_code_chunks.sql` on Postgres
- [ ] Add RAG config values to `config.py`
- [ ] Create `vector_store.py` (interface + CodeChunk dataclass)
- [ ] Create `pgvector_store.py` (adapt DB calls to match existing DB pattern)
- [ ] Create `chunker.py`
- [ ] Create `retriever.py`
- [ ] Wire indexing into `github.py` (as background job enqueue, not sync call)
- [ ] Wire retrieval into `analysis.py` with fallback to raw context
- [ ] Update `EVALUATION_INSTRUCTIONS` prompt
- [ ] Add background job processor to `jobs.py`
- [ ] Add admin endpoints
- [ ] Add `pgvector` to `pyproject.toml`
- [ ] Write tests in `test_retriever.py`
- [ ] Manual verification: sync a GitHub account → trigger analysis → confirm
  `repository_evaluations` references specific file paths from retrieval

-----

## 15. CRITICAL NOTES FOR COPILOT

- Adapt all DB calls (`self.db.execute`, `self.db.executemany`) to match the
  existing DB access pattern in the codebase. Do not introduce a new pattern.
- The fallback in `run_analysis` (raw context if RAG not ready) is not optional.
  RAG index may not exist for users who synced before this feature shipped.
- Indexing failures must never break GitHub sync. Always wrap in try/except.
- The `<=>` operator in the pgvector query is cosine distance. Ensure the
  pgvector extension is enabled before running queries or you’ll get a syntax error.
- `text-embedding-3-small` produces 1536-dimensional vectors. The `vector(1536)`
  column type must match exactly.