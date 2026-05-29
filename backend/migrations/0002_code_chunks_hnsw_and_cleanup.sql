-- HNSW index on code_chunks.embedding so per-user and (future) cross-user
-- vector search is sub-linear instead of seq-scan + cosine_distance per row.

CREATE INDEX IF NOT EXISTS code_chunks_embedding_hnsw_idx
  ON code_chunks USING hnsw (embedding vector_cosine_ops);

-- analysis_id was always written as NULL and never read with a non-NULL value;
-- drop the column and its btree index so future migrations can re-introduce a
-- meaningful per-analysis partitioning if needed.

DROP INDEX IF EXISTS ix_code_chunks_analysis_id;
ALTER TABLE code_chunks DROP COLUMN IF EXISTS analysis_id;
