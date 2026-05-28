"""Simple migration runner for SQL stubs.
Run: python backend/scripts/apply_migrations.py
This will execute any .sql files in backend/migrations in alphabetical order.
"""
from pathlib import Path
from sqlalchemy import text
from app.db import Base, engine, ensure_lightweight_migrations

MIGRATIONS_DIR = Path(__file__).resolve().parents[0] / ".." / "migrations"


def apply_migrations():
    from app import models  # noqa: F401

    if engine.dialect.name == "postgresql":
        if models.Vector is None:
            raise RuntimeError(
                "Postgres migrations require the Python 'pgvector' package. "
                "Install backend dependencies with `pip install -e .`."
            )
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=engine)
    ensure_lightweight_migrations()

    mig_dir = MIGRATIONS_DIR.resolve()
    if not mig_dir.exists():
        print("No migrations directory found.")
        return
    for sql_file in sorted(mig_dir.glob("*.sql")):
        print(f"Applying {sql_file.name}")
        with open(sql_file, "r", encoding="utf-8") as fh:
            sql = fh.read()
        with engine.begin() as conn:
            conn.execute(text(sql))
    print("Migrations applied.")


if __name__ == "__main__":
    apply_migrations()
