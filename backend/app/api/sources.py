from datetime import timedelta
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import require_user
from app.db import SessionLocal, get_db
from app.models import CodeChunk, ConnectedAccount, GitHubRepository, LeetCodeSnapshot, SourceKind, User
from app.schemas import GitHubConnectIn, LeetCodeConnectIn, RepositoryOut, RepositorySelectionIn, SourceOut
from app.services.embeddings import embed_repo_files_report, repo_has_embeddings
from app.services.github import delete_github_source, fetch_repo_code_context, get_github_access_token, sync_github
from app.services.leetcode import delete_leetcode_source, sync_leetcode
from app.services.refresh_policy import assert_free_tier_refresh_allowed, free_tier_refresh_days, next_free_tier_refresh_at

router = APIRouter(prefix="/sources", tags=["sources"])
logger = logging.getLogger(__name__)
EMBEDDING_LOG_PATH = Path(__file__).resolve().parents[3] / "personal" / "embedding_updates.txt"


def log_embedding_update(message: str, level: int = logging.INFO) -> None:
    logger.log(level, message)
    try:
        EMBEDDING_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with EMBEDDING_LOG_PATH.open("a", encoding="utf-8") as log_file:
            from datetime import datetime

            log_file.write(f"{datetime.utcnow().isoformat()}Z {message}\n")
    except OSError as exc:
        logger.warning("Could not write embedding update log: %s", exc)


def precompute_repo_embeddings(db: Session, user_id: str, repository_ids: list[str]) -> None:
    log_embedding_update(f"Embedding precompute started for user={user_id} repos={len(repository_ids)}")
    repos = (
        db.query(GitHubRepository)
        .filter(GitHubRepository.user_id == user_id, GitHubRepository.id.in_(repository_ids))
        .all()
    )
    log_embedding_update(f"Embedding precompute loaded {len(repos)} repo record(s) for user={user_id}")
    user = db.get(User, user_id)
    access_token = get_github_access_token(db, user) if user else None
    for repo in repos:
        if repo_has_embeddings(db, user_id, repo.id):
            log_embedding_update(f"Embedding skipped for {repo.full_name}: existing chunks found")
            continue

        context = repo.code_analysis_snapshot if isinstance(repo.code_analysis_snapshot, dict) else None
        if context is None:
            try:
                log_embedding_update(f"Fetching code context for {repo.full_name}")
                context = fetch_repo_code_context(repo.full_name, access_token)
                repo.code_analysis_snapshot = context
                db.commit()
                key_file_count = len(context.get("key_files") or []) if isinstance(context, dict) else 0
                log_embedding_update(f"Fetched code context for {repo.full_name}: key_files={key_file_count}")
            except Exception as exc:
                db.rollback()
                log_embedding_update(f"Code context fetch failed for {repo.full_name}: {exc}", logging.WARNING)
                continue

        try:
            log_embedding_update(f"Embedding started for {repo.full_name}")
            report = embed_repo_files_report(db=db, user_id=user_id, repo_id=repo.id, code_context=context)
            log_embedding_update(
                f"Embedding finished for {repo.full_name}: "
                f"chunks_pending={report.get('chunks_pending', 0)} chunks_stored={report.get('chunks_stored', 0)}"
            )
            if report.get("errors"):
                log_embedding_update(
                    f"Embedding completed with errors for {repo.full_name}: {report['errors']}",
                    logging.WARNING,
                )
        except Exception as exc:
            db.rollback()
            log_embedding_update(f"Embedding failed for {repo.full_name}: {exc}", logging.WARNING)
    log_embedding_update(f"Embedding precompute completed for user={user_id}")


def precompute_repo_embeddings_background(user_id: str, repository_ids: list[str]) -> None:
    db = SessionLocal()
    try:
        precompute_repo_embeddings(db, user_id, repository_ids)
    finally:
        db.close()


def repository_out(repo: GitHubRepository, embedded_chunk_count: int = 0) -> RepositoryOut:
    if not repo.selected_for_analysis:
        embedding_status = "not_selected"
    elif embedded_chunk_count > 0:
        embedding_status = "embedded"
    else:
        embedding_status = "pending"

    return RepositoryOut(
        id=repo.id,
        full_name=repo.full_name,
        description=repo.description,
        language=repo.language,
        stars=repo.stars,
        forks=repo.forks,
        open_issues=repo.open_issues,
        commit_count=repo.commit_count,
        selected_for_analysis=repo.selected_for_analysis,
        pushed_at=repo.pushed_at,
        code_analysis_available=isinstance(repo.code_analysis_snapshot, dict),
        embedded_chunk_count=embedded_chunk_count,
        embedding_status=embedding_status,
    )


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
def list_github_repositories(db: Session = Depends(get_db), user: User = Depends(require_user)) -> list[RepositoryOut]:
    repos = (
        db.query(GitHubRepository)
        .filter(GitHubRepository.user_id == user.id)
        .order_by(GitHubRepository.selected_for_analysis.desc(), GitHubRepository.stars.desc(), GitHubRepository.pushed_at.desc())
        .all()
    )
    repo_ids = [repo.id for repo in repos]
    chunk_counts = {
        repo_id: count
        for repo_id, count in (
            db.query(CodeChunk.repo_id, func.count(CodeChunk.id))
            .filter(CodeChunk.user_id == user.id, CodeChunk.repo_id.in_(repo_ids))
            .group_by(CodeChunk.repo_id)
            .all()
            if repo_ids
            else []
        )
    }
    return [repository_out(repo, int(chunk_counts.get(repo.id, 0) or 0)) for repo in repos]


@router.post("/github/repositories/selection", response_model=list[RepositoryOut])
def select_github_repositories(
    payload: RepositorySelectionIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> list[RepositoryOut]:
    repository_ids = set(payload.repository_ids[:20])
    repos = db.query(GitHubRepository).filter(GitHubRepository.user_id == user.id).all()
    owned_ids = {repo.id for repo in repos}
    invalid = repository_ids - owned_ids
    if invalid:
        raise HTTPException(status_code=404, detail="One or more repositories were not found")
    for repo in repos:
        repo.selected_for_analysis = repo.id in repository_ids
    db.commit()

    if repository_ids:
        background_tasks.add_task(precompute_repo_embeddings_background, user.id, list(repository_ids))
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
