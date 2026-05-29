from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from jose import jwt

from app.auth import get_current_user, get_or_create_user, slugify
from app.models import User
from app.schemas import CurrentUser


def settings_stub(*, trust_dev_headers=True, secret="test-secret"):
    return SimpleNamespace(auth_trust_dev_headers=trust_dev_headers, backend_session_secret=secret)


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("Ada Lovelace", "ada-lovelace"),
        ("Ada   Lovelace", "ada-lovelace"),
        ("Grace_Hopper!!", "grace-hopper"),
        ("---trim-me---", "trim-me"),
        ("CamelCase123", "camelcase123"),
    ],
)
def test_slugify_normalizes_text(value, expected):
    assert slugify(value) == expected


def test_slugify_falls_back_to_developer_for_empty():
    assert slugify("") == "developer"
    assert slugify("!!!") == "developer"


def test_slugify_truncates_to_80_chars():
    assert len(slugify("a" * 200)) == 80


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------


def test_get_current_user_trusts_dev_headers(monkeypatch):
    monkeypatch.setattr("app.auth.get_settings", lambda: settings_stub(trust_dev_headers=True))
    user = get_current_user(
        authorization=None,
        x_cipher_user_id="dev-1",
        x_cipher_user_email="dev@example.com",
        x_cipher_user_name="Dev User",
    )
    assert user == CurrentUser(id="dev-1", email="dev@example.com", name="Dev User")


def test_get_current_user_ignores_dev_headers_when_disabled(monkeypatch):
    monkeypatch.setattr("app.auth.get_settings", lambda: settings_stub(trust_dev_headers=False))
    with pytest.raises(HTTPException) as exc:
        get_current_user(authorization=None, x_cipher_user_id="dev-1")
    assert exc.value.status_code == 401


def test_get_current_user_requires_bearer_prefix(monkeypatch):
    monkeypatch.setattr("app.auth.get_settings", lambda: settings_stub(trust_dev_headers=False))
    with pytest.raises(HTTPException) as exc:
        get_current_user(authorization="token-without-bearer")
    assert exc.value.status_code == 401


def test_get_current_user_decodes_valid_jwt(monkeypatch):
    monkeypatch.setattr("app.auth.get_settings", lambda: settings_stub(trust_dev_headers=False))
    token = jwt.encode({"sub": "u-42", "email": "a@b.c", "name": "Ada"}, "test-secret", algorithm="HS256")
    user = get_current_user(authorization=f"Bearer {token}")
    assert user == CurrentUser(id="u-42", email="a@b.c", name="Ada")


def test_get_current_user_rejects_invalid_jwt(monkeypatch):
    monkeypatch.setattr("app.auth.get_settings", lambda: settings_stub(trust_dev_headers=False))
    with pytest.raises(HTTPException) as exc:
        get_current_user(authorization="Bearer not-a-real-token")
    assert exc.value.status_code == 401


def test_get_current_user_rejects_token_without_subject(monkeypatch):
    monkeypatch.setattr("app.auth.get_settings", lambda: settings_stub(trust_dev_headers=False))
    token = jwt.encode({"email": "a@b.c"}, "test-secret", algorithm="HS256")
    with pytest.raises(HTTPException) as exc:
        get_current_user(authorization=f"Bearer {token}")
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# get_or_create_user
# ---------------------------------------------------------------------------


def test_get_or_create_user_returns_existing(db_session):
    existing = User(id="u-1", email="x@y.z", name="Existing", slug="existing")
    db_session.add(existing)
    db_session.commit()

    result = get_or_create_user(db_session, CurrentUser(id="u-1", email="ignored@y.z", name="Ignored"))
    assert result.id == "u-1"
    assert result.name == "Existing"


def test_get_or_create_user_creates_from_name(db_session):
    result = get_or_create_user(db_session, CurrentUser(id="u-2", email="dev@example.com", name="Grace Hopper"))
    assert result.id == "u-2"
    assert result.slug == "grace-hopper"
    assert db_session.get(User, "u-2") is not None


def test_get_or_create_user_slug_falls_back_to_email_local_part(db_session):
    result = get_or_create_user(db_session, CurrentUser(id="u-3", email="katherine@nasa.gov", name=None))
    assert result.slug == "katherine"


def test_get_or_create_user_slug_falls_back_to_id(db_session):
    result = get_or_create_user(db_session, CurrentUser(id="u-4", email=None, name=None))
    assert result.slug == "u-4"
