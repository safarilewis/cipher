from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def new_id() -> str:
    return uuid4().hex


class SourceKind(str, Enum):
    github = "github"
    leetcode = "leetcode"


class AnalysisStatus(str, Enum):
    queued = "queued"
    running = "running"
    ready = "ready"
    failed = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    headline: Mapped[str | None] = mapped_column(String(255))
    career_stage_override: Mapped[str | None] = mapped_column(String(40))
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    accounts: Mapped[list["ConnectedAccount"]] = relationship(cascade="all, delete-orphan")
    sections: Mapped[list["ProfileSection"]] = relationship(cascade="all, delete-orphan")
    repositories: Mapped[list["GitHubRepository"]] = relationship(cascade="all, delete-orphan")
    leetcode_snapshots: Mapped[list["LeetCodeSnapshot"]] = relationship(cascade="all, delete-orphan")
    analyses: Mapped[list["GeneratedEvaluation"]] = relationship(cascade="all, delete-orphan")


class ConnectedAccount(Base):
    __tablename__ = "connected_accounts"
    __table_args__ = (UniqueConstraint("user_id", "kind", name="uq_user_source"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[SourceKind] = mapped_column(SAEnum(SourceKind))
    external_username: Mapped[str] = mapped_column(String(255))
    access_token: Mapped[str | None] = mapped_column(Text)
    raw_snapshot: Mapped[dict | None] = mapped_column(JSON)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProfileSection(Base):
    __tablename__ = "profile_sections"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(255))
    organization: Mapped[str | None] = mapped_column(String(255))
    start_date: Mapped[str | None] = mapped_column(String(40))
    end_date: Mapped[str | None] = mapped_column(String(40))
    description: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(500))
    order: Mapped[int] = mapped_column(Integer, default=0)


class GitHubRepository(Base):
    __tablename__ = "github_repositories"
    __table_args__ = (UniqueConstraint("user_id", "full_name", name="uq_user_repo"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(80))
    stars: Mapped[int] = mapped_column(Integer, default=0)
    forks: Mapped[int] = mapped_column(Integer, default=0)
    open_issues: Mapped[int] = mapped_column(Integer, default=0)
    commit_count: Mapped[int] = mapped_column(Integer, default=0)
    all_time_commit_count: Mapped[int] = mapped_column(Integer, default=0)
    selected_for_analysis: Mapped[bool] = mapped_column(Boolean, default=False)
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime)
    code_analysis_snapshot: Mapped[dict | None] = mapped_column(JSON)
    raw: Mapped[dict | None] = mapped_column(JSON)


class LeetCodeSnapshot(Base):
    __tablename__ = "leetcode_snapshots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    username: Mapped[str] = mapped_column(String(255), index=True)
    total_solved: Mapped[int] = mapped_column(Integer, default=0)
    easy_solved: Mapped[int] = mapped_column(Integer, default=0)
    medium_solved: Mapped[int] = mapped_column(Integer, default=0)
    hard_solved: Mapped[int] = mapped_column(Integer, default=0)
    ranking: Mapped[int | None] = mapped_column(Integer)
    raw: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GeneratedEvaluation(Base):
    __tablename__ = "generated_evaluations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[AnalysisStatus] = mapped_column(SAEnum(AnalysisStatus), default=AnalysisStatus.queued)
    summary: Mapped[str | None] = mapped_column(Text)
    skill_model: Mapped[dict | None] = mapped_column(JSON)
    skill_model_v2: Mapped[dict | None] = mapped_column(JSON)
    career_stage: Mapped[dict | None] = mapped_column(JSON)
    signal_completeness: Mapped[dict | None] = mapped_column(JSON)
    profile_signal_snapshot: Mapped[dict | None] = mapped_column(JSON)
    repository_evaluations: Mapped[list | None] = mapped_column(JSON)
    strengths: Mapped[list | None] = mapped_column(JSON)
    growth_areas: Mapped[list | None] = mapped_column(JSON)
    project_complexity_notes: Mapped[list | None] = mapped_column(JSON)
    evidence_highlights: Mapped[list | None] = mapped_column(JSON)
    recruiter_copy: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


try:
    from pgvector.sqlalchemy import Vector  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - local test envs may not install optional pgvector
    Vector = None


class CodeChunk(Base):
    __tablename__ = "code_chunks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    repo_id: Mapped[str] = mapped_column(ForeignKey("github_repositories.id"), index=True)
    file_path: Mapped[str] = mapped_column(String(500))
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column((Vector(1536) if Vector is not None else JSON), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProfileEmbedding(Base):
    __tablename__ = "profile_embeddings"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    source_text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column((Vector(1536) if Vector is not None else JSON), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
