-- profile_embeddings: one row per user, holds a single 1536-dim summary embedding
-- that powers cross-user recruiter search. The HNSW index makes ranked retrieval
-- sub-linear; without it search would seq-scan every profile.

CREATE TABLE IF NOT EXISTS profile_embeddings (
  user_id VARCHAR(64) PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  source_text TEXT,
  embedding vector(1536),
  summary TEXT,
  updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS profile_embeddings_embedding_hnsw_idx
  ON profile_embeddings USING hnsw (embedding vector_cosine_ops);
