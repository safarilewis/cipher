from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AnalysisStatus, GeneratedEvaluation, GitHubRepository, LeetCodeSnapshot, ProfileSection, User
from app.schemas import PublicProfileOut
from app.services.embeddings import search_profiles

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/search")
def search_developer_profiles(
    q: str = Query(..., min_length=1, max_length=500, description="Natural-language search query"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> dict:
    return {"query": q, "results": search_profiles(db, query=q, limit=limit, published_only=True)}


@router.get("/profiles/{slug}", response_model=PublicProfileOut)
def get_public_profile(slug: str, db: Session = Depends(get_db)) -> PublicProfileOut:
    user = db.query(User).filter(User.slug == slug, User.published.is_(True)).one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Profile not found")

    evaluation = (
        db.query(GeneratedEvaluation)
        .filter(
            GeneratedEvaluation.user_id == user.id,
            GeneratedEvaluation.reviewed.is_(True),
            GeneratedEvaluation.status == AnalysisStatus.ready,
        )
        .order_by(GeneratedEvaluation.created_at.desc())
        .first()
    )
    sections = db.query(ProfileSection).filter(ProfileSection.user_id == user.id).order_by(ProfileSection.order).all()
    repositories = db.query(GitHubRepository).filter(GitHubRepository.user_id == user.id).all()
    leetcode = (
        db.query(LeetCodeSnapshot)
        .filter(LeetCodeSnapshot.user_id == user.id)
        .order_by(LeetCodeSnapshot.created_at.desc())
        .first()
    )
    return PublicProfileOut(
        user=user,
        sections=sections,
        repositories=repositories,
        leetcode=leetcode,
        evaluation=evaluation,
    )

