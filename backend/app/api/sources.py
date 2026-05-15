from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_user
from app.db import get_db
from app.models import ConnectedAccount, GitHubRepository, LeetCodeSnapshot, SourceKind, User
from app.schemas import GitHubConnectIn, LeetCodeConnectIn, RepositoryOut, RepositorySelectionIn, SourceOut
from app.services.github import delete_github_source, sync_github
from app.services.leetcode import delete_leetcode_source, sync_leetcode
from app.services.refresh_policy import assert_free_tier_refresh_allowed, free_tier_refresh_days, next_free_tier_refresh_at

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceOut])
def list_sources(db: Session = Depends(get_db), user: User = Depends(require_user)) -> list[SourceOut]:
    accounts = db.query(ConnectedAccount).filter(ConnectedAccount.user_id == user.id).all()
    output = []
    for account in accounts:
        summary = account.raw_snapshot if isinstance(account.raw_snapshot, dict) else None
        output.append(
            SourceOut(
                kind=account.kind,
                external_username=account.external_username,
                last_synced_at=account.last_synced_at,
                summary={
                    **(summary or {}),
                    "refresh_interval_days": free_tier_refresh_days(),
                    "next_refresh_at": (
                        next_free_tier_refresh_at(account).isoformat()
                        if next_free_tier_refresh_at(account)
                        else None
                    ),
                },
            )
        )
    return output


@router.get("/github/repositories", response_model=list[RepositoryOut])
def list_github_repositories(db: Session = Depends(get_db), user: User = Depends(require_user)) -> list[GitHubRepository]:
    return (
        db.query(GitHubRepository)
        .filter(GitHubRepository.user_id == user.id)
        .order_by(GitHubRepository.selected_for_analysis.desc(), GitHubRepository.stars.desc(), GitHubRepository.pushed_at.desc())
        .all()
    )


@router.post("/github/repositories/selection", response_model=list[RepositoryOut])
def select_github_repositories(
    payload: RepositorySelectionIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> list[GitHubRepository]:
    repository_ids = set(payload.repository_ids[:5])
    repos = db.query(GitHubRepository).filter(GitHubRepository.user_id == user.id).all()
    owned_ids = {repo.id for repo in repos}
    invalid = repository_ids - owned_ids
    if invalid:
        raise HTTPException(status_code=404, detail="One or more repositories were not found")
    for repo in repos:
        repo.selected_for_analysis = repo.id in repository_ids
    db.commit()
    return list_github_repositories(db, user)


@router.post("/github", response_model=SourceOut)
async def connect_github(
    payload: GitHubConnectIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> SourceOut:
    existing = (
        db.query(ConnectedAccount)
        .filter(ConnectedAccount.user_id == user.id, ConnectedAccount.kind == SourceKind.github)
        .one_or_none()
    )
    assert_free_tier_refresh_allowed(existing)
    account = await sync_github(db, user, payload.username, payload.access_token)
    return SourceOut(
        kind=account.kind,
        external_username=account.external_username,
        last_synced_at=account.last_synced_at,
        summary={
            **(account.raw_snapshot or {}),
            "refresh_interval_days": free_tier_refresh_days(),
            "next_refresh_at": next_free_tier_refresh_at(account).isoformat() if next_free_tier_refresh_at(account) else None,
        },
    )


@router.post("/leetcode", response_model=SourceOut)
async def connect_leetcode(
    payload: LeetCodeConnectIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> SourceOut:
    existing = (
        db.query(ConnectedAccount)
        .filter(ConnectedAccount.user_id == user.id, ConnectedAccount.kind == SourceKind.leetcode)
        .one_or_none()
    )
    assert_free_tier_refresh_allowed(existing)
    try:
        snapshot = await sync_leetcode(db, user, payload.username)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SourceOut(
        kind=SourceKind.leetcode,
        external_username=snapshot.username,
        last_synced_at=snapshot.created_at,
        summary={
            "total_solved": snapshot.total_solved,
            "easy_solved": snapshot.easy_solved,
            "medium_solved": snapshot.medium_solved,
            "hard_solved": snapshot.hard_solved,
            "ranking": snapshot.ranking,
            "refresh_interval_days": free_tier_refresh_days(),
            "next_refresh_at": (snapshot.created_at + timedelta(days=free_tier_refresh_days())).isoformat(),
        },
    )


@router.delete("/{kind}", status_code=204)
def delete_source(kind: SourceKind, db: Session = Depends(get_db), user: User = Depends(require_user)) -> None:
    if kind == SourceKind.github:
        delete_github_source(db, user)
    if kind == SourceKind.leetcode:
        delete_leetcode_source(db, user)


@router.get("/leetcode/latest")
def latest_leetcode(db: Session = Depends(get_db), user: User = Depends(require_user)) -> dict:
    snapshot = (
        db.query(LeetCodeSnapshot)
        .filter(LeetCodeSnapshot.user_id == user.id)
        .order_by(LeetCodeSnapshot.created_at.desc())
        .first()
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail="No LeetCode snapshot found")
    return {
        "username": snapshot.username,
        "total_solved": snapshot.total_solved,
        "easy_solved": snapshot.easy_solved,
        "medium_solved": snapshot.medium_solved,
        "hard_solved": snapshot.hard_solved,
        "ranking": snapshot.ranking,
    }
