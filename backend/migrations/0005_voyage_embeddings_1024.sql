-- Switch stored embeddings from OpenAI text-embedding-3-small (1536 dims) to
-- Voyage voyage-2 (1024 dims). Existing embeddings are derived/cache data, so
-- delete them before changing the vector column dimensions.

DROP INDEX IF EXISTS code_chunks_embedding_hnsw_idx;
DROP INDEX IF EXISTS profile_embeddings_embedding_hnsw_idx;

DELETE FROM code_chunks;
DELETE FROM profile_embeddings;

ALTER TABLE code_chunks
  ALTER COLUMN embedding TYPE vector(1024);

ALTER TABLE profile_embeddings
  ALTER COLUMN embedding TYPE vector(1024);

CREATE INDEX IF NOT EXISTS code_chunks_embedding_hnsw_idx
  ON code_chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS profile_embeddings_embedding_hnsw_idx
  ON profile_embeddings USING hnsw (embedding vector_cosine_ops);
