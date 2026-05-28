from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models

    # Ensure pgvector extension exists for Postgres before creating tables
    if engine.dialect.name == "postgresql":
        if models.Vector is None:
            raise RuntimeError(
                "Postgres RAG storage requires the Python 'pgvector' package. "
                "Install backend dependencies with `pip install -e .`."
            )
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=engine)
    ensure_lightweight_migrations()


def ensure_lightweight_migrations() -> None:
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "users" in table_names:
        migrate_users_table(inspector)
    if "generated_evaluations" in table_names:
        migrate_generated_evaluations_table(inspector)
    if "github_repositories" not in table_names:
        return

    existing = {column["name"] for column in inspector.get_columns("github_repositories")}
    statements = []
    if "commit_count" not in existing:
        statements.append("ALTER TABLE github_repositories ADD COLUMN commit_count INTEGER DEFAULT 0")
    if "all_time_commit_count" not in existing:
        statements.append("ALTER TABLE github_repositories ADD COLUMN all_time_commit_count INTEGER DEFAULT 0")
    if "selected_for_analysis" not in existing:
        statements.append("ALTER TABLE github_repositories ADD COLUMN selected_for_analysis BOOLEAN DEFAULT FALSE")
    if "code_analysis_snapshot" not in existing:
        if engine.dialect.name == "postgresql":
            statements.append("ALTER TABLE github_repositories ADD COLUMN code_analysis_snapshot JSON")
        else:
            statements.append("ALTER TABLE github_repositories ADD COLUMN code_analysis_snapshot JSON")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
        connection.execute(text("UPDATE github_repositories SET commit_count = 0 WHERE commit_count IS NULL"))
        connection.execute(text("UPDATE github_repositories SET all_time_commit_count = 0 WHERE all_time_commit_count IS NULL"))
        connection.execute(text("UPDATE github_repositories SET selected_for_analysis = FALSE WHERE selected_for_analysis IS NULL"))


def migrate_users_table(inspector) -> None:
    existing = {column["name"] for column in inspector.get_columns("users")}
    if "career_stage_override" in existing:
        return
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN career_stage_override VARCHAR(40)"))


def migrate_generated_evaluations_table(inspector) -> None:
    existing = {column["name"] for column in inspector.get_columns("generated_evaluations")}
    statements = []
    for column in ("skill_model_v2", "career_stage", "signal_completeness", "profile_signal_snapshot", "repository_evaluations"):
        if column not in existing:
            statements.append(f"ALTER TABLE generated_evaluations ADD COLUMN {column} JSON")
    if not statements:
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
