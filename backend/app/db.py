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
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ensure_lightweight_migrations()


def ensure_lightweight_migrations() -> None:
    inspector = inspect(engine)
    if "github_repositories" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("github_repositories")}
    statements = []
    if "commit_count" not in existing:
        statements.append("ALTER TABLE github_repositories ADD COLUMN commit_count INTEGER DEFAULT 0")
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
        connection.execute(text("UPDATE github_repositories SET selected_for_analysis = FALSE WHERE selected_for_analysis IS NULL"))
