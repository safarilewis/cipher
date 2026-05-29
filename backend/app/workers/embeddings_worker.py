"""Embeddings worker scaffold using RQ (Redis Queue).
This is a simple example; adapt to Celery or your preferred background system.

To enqueue an embedding job from application code:
from redis import Redis
from rq import Queue
from app.workers.embeddings_worker import enqueue_embedding_job

redis_conn = Redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379'))
q = Queue(connection=redis_conn)
q.enqueue(enqueue_embedding_job, db_session_args)

Run the worker:
rq worker --with-scheduler
"""
from typing import Any
import os
import logging

from redis import Redis
from rq import Queue

from app.services.embeddings import embed_repo_files

logger = logging.getLogger(__name__)

redis_conn = Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379"))
queue = Queue("embeddings", connection=redis_conn)


def enqueue_embedding_job(user_id: str, repo_id: str, code_context: dict) -> None:
    """Worker entrypoint: reconstruct a DB session and run embedding.
    This is executed inside the worker process.
    """
    try:
        from app.db import SessionLocal

        db = SessionLocal()
        try:
            embed_repo_files(db=db, user_id=user_id, repo_id=repo_id, code_context=code_context)
        finally:
            db.close()
    except Exception:
        logger.exception("Embedding job failed for %s/%s", user_id, repo_id)


if __name__ == "__main__":
    print("This module contains worker helpers for embeddings. Run an RQ worker to execute jobs.")
