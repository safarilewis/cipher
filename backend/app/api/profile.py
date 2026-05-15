from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_user
from app.db import get_db
from app.models import ProfileSection, User
from app.schemas import ProfileUpdate, SectionIn, SectionOut, UserOut

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=UserOut)
def get_profile(user: User = Depends(require_user)) -> User:
    return user


@router.patch("", response_model=UserOut)
def update_profile(payload: ProfileUpdate, db: Session = Depends(get_db), user: User = Depends(require_user)) -> User:
    if payload.name is not None:
        user.name = payload.name
    if payload.headline is not None:
        user.headline = payload.headline
    if payload.slug is not None:
        user.slug = payload.slug
    if "career_stage_override" in payload.model_fields_set:
        user.career_stage_override = payload.career_stage_override
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Slug is already taken") from exc
    db.refresh(user)
    return user


@router.get("/sections", response_model=list[SectionOut])
def list_sections(db: Session = Depends(get_db), user: User = Depends(require_user)) -> list[ProfileSection]:
    return db.query(ProfileSection).filter(ProfileSection.user_id == user.id).order_by(ProfileSection.order).all()


@router.post("/sections", response_model=SectionOut, status_code=201)
def create_section(payload: SectionIn, db: Session = Depends(get_db), user: User = Depends(require_user)) -> ProfileSection:
    section = ProfileSection(user_id=user.id, **payload.model_dump())
    db.add(section)
    db.commit()
    db.refresh(section)
    return section


@router.put("/sections/{section_id}", response_model=SectionOut)
def update_section(
    section_id: str,
    payload: SectionIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> ProfileSection:
    section = db.get(ProfileSection, section_id)
    if not section or section.user_id != user.id:
        raise HTTPException(status_code=404, detail="Section not found")
    for key, value in payload.model_dump().items():
        setattr(section, key, value)
    db.commit()
    db.refresh(section)
    return section


@router.delete("/sections/{section_id}", status_code=204)
def delete_section(section_id: str, db: Session = Depends(get_db), user: User = Depends(require_user)) -> None:
    section = db.get(ProfileSection, section_id)
    if not section or section.user_id != user.id:
        raise HTTPException(status_code=404, detail="Section not found")
    db.delete(section)
    db.commit()
