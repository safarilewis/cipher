import logging
from datetime import datetime, timedelta
from threading import Thread

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_user
from app.db import SessionLocal, get_db
from app.models import AnalysisStatus, GeneratedEvaluation, User
from app.schemas import EvaluationOut
from app.services.analysis import run_analysis

router = APIRouter(prefix="/analysis", tags=["analysis"])
logger = logging.getLogger(__name__)
STALE_RUNNING_AFTER = timedelta(minutes=3)


def run_analysis_background(user_id: str, evaluation_id: str) -> None:
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        evaluation = db.get(GeneratedEvaluation, evaluation_id)
        if not user or not evaluation:
            logger.warning("Skipped background analysis; user=%s evaluation=%s not found", user_id, evaluation_id)
            return
        run_analysis(db, user, evaluation)
    except Exception as exc:  # pragma: no cover - defensive guard around the background runner itself
        logger.exception("Background analysis failed for evaluation %s", evaluation_id)
        try:
            evaluation = db.get(GeneratedEvaluation, evaluation_id)
            if evaluation:
                evaluation.status = AnalysisStatus.failed
                evaluation.error = str(exc)
                db.commit()
        except Exception:
            logger.exception("Failed to persist background analysis failure for evaluation %s", evaluation_id)
            db.rollback()
    finally:
        db.close()


def start_analysis_worker(user_id: str, evaluation_id: str) -> None:
    worker = Thread(target=run_analysis_background, args=(user_id, evaluation_id), daemon=False)
    worker.start()


@router.get("/latest", response_model=EvaluationOut | None)
def latest_analysis(db: Session = Depends(get_db), user: User = Depends(require_user)) -> GeneratedEvaluation | None:
    active_evaluation = (
        db.query(GeneratedEvaluation)
        .filter(
            GeneratedEvaluation.user_id == user.id,
            GeneratedEvaluation.status.in_([AnalysisStatus.queued, AnalysisStatus.running]),
        )
        .order_by(GeneratedEvaluation.created_at.desc())
        .first()
    )
    if active_evaluation:
        return active_evaluation

    ready_evaluation = (
        db.query(GeneratedEvaluation)
        .filter(GeneratedEvaluation.user_id == user.id, GeneratedEvaluation.status == AnalysisStatus.ready)
        .order_by(GeneratedEvaluation.created_at.desc())
        .first()
    )
    if ready_evaluation:
        return ready_evaluation

    return (
        db.query(GeneratedEvaluation)
        .filter(GeneratedEvaluation.user_id == user.id)
        .order_by(GeneratedEvaluation.created_at.desc())
        .first()
    )


@router.post("", response_model=EvaluationOut, status_code=status.HTTP_202_ACCEPTED)
def create_analysis(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> GeneratedEvaluation:
    try:
        active_evaluation = (
            db.query(GeneratedEvaluation)
            .filter(
                GeneratedEvaluation.user_id == user.id,
                GeneratedEvaluation.status.in_([AnalysisStatus.queued, AnalysisStatus.running]),
            )
            .order_by(GeneratedEvaluation.created_at.desc())
            .first()
        )
        if active_evaluation:
            is_queued = active_evaluation.status == AnalysisStatus.queued
            is_stale_running = (
                active_evaluation.status == AnalysisStatus.running
                and active_evaluation.updated_at
                and datetime.utcnow() - active_evaluation.updated_at > STALE_RUNNING_AFTER
            )
            if is_queued or is_stale_running:
                active_evaluation.status = AnalysisStatus.queued
                active_evaluation.error = None
                active_evaluation.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(active_evaluation)
                start_analysis_worker(user.id, active_evaluation.id)
            return active_evaluation

        evaluation = GeneratedEvaluation(user_id=user.id, status=AnalysisStatus.queued)
        db.add(evaluation)
        db.commit()
        db.refresh(evaluation)
        start_analysis_worker(user.id, evaluation.id)
        return evaluation
    except Exception as exc:
        logger.exception("Analysis creation failed for user %s", user.id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{evaluation_id}/review", response_model=EvaluationOut)
def mark_reviewed(
    evaluation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> GeneratedEvaluation:
    evaluation = db.get(GeneratedEvaluation, evaluation_id)
    if not evaluation or evaluation.user_id != user.id:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    if evaluation.status != AnalysisStatus.ready:
        raise HTTPException(status_code=409, detail="Only ready evaluations can be reviewed")
    evaluation.reviewed = True
    db.commit()
    db.refresh(evaluation)
    return evaluation


@router.post("/publish", response_model=dict)
def publish_profile(db: Session = Depends(get_db), user: User = Depends(require_user)) -> dict:
    evaluation = (
        db.query(GeneratedEvaluation)
        .filter(GeneratedEvaluation.user_id == user.id, GeneratedEvaluation.reviewed.is_(True))
        .order_by(GeneratedEvaluation.created_at.desc())
        .first()
    )
    if not evaluation:
        raise HTTPException(status_code=409, detail="Review an analysis before publishing")
    user.published = True
    db.commit()
    return {"published": True, "slug": user.slug}


@router.post("/unpublish", response_model=dict)
def unpublish_profile(db: Session = Depends(get_db), user: User = Depends(require_user)) -> dict:
    user.published = False
    db.commit()
    return {"published": False, "slug": user.slug}
