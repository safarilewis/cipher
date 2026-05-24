from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import get_db
from app.models import User
from app.schemas import CurrentUser


def slugify(value: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug[:80] or "developer"


def get_current_user(
    authorization: str | None = Header(default=None),
    x_cipher_user_id: str | None = Header(default=None),
    x_cipher_user_email: str | None = Header(default=None),
    x_cipher_user_name: str | None = Header(default=None),
) -> CurrentUser:
    settings = get_settings()
    if settings.auth_trust_dev_headers and x_cipher_user_id:
        return CurrentUser(id=x_cipher_user_id, email=x_cipher_user_email, name=x_cipher_user_name)

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, settings.backend_session_secret, algorithms=["HS256"])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token") from exc

    subject = payload.get("sub")
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing subject")
    return CurrentUser(id=subject, email=payload.get("email"), name=payload.get("name"))


def get_or_create_user(db: Session, current: CurrentUser) -> User:
    user = db.get(User, current.id)
    if user:
        return user

    base = current.name or (current.email.split("@")[0] if current.email else current.id)
    user = User(id=current.id, email=current.email, name=current.name, slug=slugify(base))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def require_user(
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    return get_or_create_user(db, current)

