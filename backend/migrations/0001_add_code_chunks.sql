-- Migration stub: create code_chunks table and pgvector index
-- Run this manually or integrate into your Alembic migrations.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS code_chunks (
  id VARCHAR(32) PRIMARY KEY,
  user_id VARCHAR(64) REFERENCES users(id),
  repo_id VARCHAR(32) REFERENCES github_repositories(id),
  analysis_id VARCHAR(32),
  file_path VARCHAR(500),
  chunk_index INTEGER DEFAULT 0,
  content TEXT,
  embedding vector(1536),
  created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
  CONSTRAINT uq_repo_file_chunk UNIQUE (repo_id, file_path, chunk_index)
);

-- Example: create ivfflat or hnsw index depending on pgvector version
-- CREATE INDEX IF NOT EXISTS code_chunks_embedding_idx ON code_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
