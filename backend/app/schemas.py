from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models import AnalysisStatus, SourceKind


class CurrentUser(BaseModel):
    id: str
    email: str | None = None
    name: str | None = None


class UserOut(BaseModel):
    id: str
    email: str | None
    name: str | None
    slug: str
    headline: str | None
    career_stage_override: Literal["student", "new_grad", "early", "mid", "senior"] | None = None
    published: bool

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    name: str | None = None
    headline: str | None = None
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9-]{3,80}$")
    career_stage_override: Literal["student", "new_grad", "early", "mid", "senior"] | None = None


class SectionIn(BaseModel):
    kind: Literal["education", "experience", "certification", "bootcamp", "project"]
    title: str
    organization: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None
    url: str | None = None
    order: int = 0


class SectionOut(SectionIn):
    id: str

    model_config = {"from_attributes": True}


class GitHubConnectIn(BaseModel):
    username: str
    access_token: str | None = None


class LeetCodeConnectIn(BaseModel):
    username: str


class SourceOut(BaseModel):
    kind: SourceKind
    external_username: str
    last_synced_at: datetime | None
    summary: dict[str, Any] | None = None


class RepositoryOut(BaseModel):
    id: str
    full_name: str
    description: str | None
    language: str | None
    stars: int
    forks: int
    open_issues: int
    commit_count: int
    selected_for_analysis: bool
    pushed_at: datetime | None

    model_config = {"from_attributes": True}


class RepositorySelectionIn(BaseModel):
    repository_ids: list[str] = Field(default_factory=list, max_length=10)


class LeetCodeSnapshotOut(BaseModel):
    username: str
    total_solved: int
    easy_solved: int
    medium_solved: int
    hard_solved: int
    ranking: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class EvaluationOut(BaseModel):
    id: str
    status: AnalysisStatus
    summary: str | None
    skill_model: dict | None
    skill_model_v2: dict | None = None
    career_stage: dict | None = None
    signal_completeness: dict | None = None
    repository_evaluations: list | None = None
    strengths: list | None
    growth_areas: list | None
    project_complexity_notes: list | None
    evidence_highlights: list | None
    recruiter_copy: str | None
    error: str | None
    reviewed: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PublicProfileOut(BaseModel):
    user: UserOut
    sections: list[SectionOut]
    repositories: list[RepositoryOut]
    leetcode: LeetCodeSnapshotOut | None
    evaluation: EvaluationOut | None
