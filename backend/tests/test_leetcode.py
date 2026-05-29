import pytest

from app.models import ConnectedAccount, LeetCodeSnapshot, SourceKind, User
from app.services import leetcode
from app.services.leetcode import (
    counts_by_difficulty,
    delete_leetcode_source,
    fetch_leetcode_profile,
    sync_leetcode,
)


SAMPLE_PROFILE = {
    "username": "ada",
    "profile": {"ranking": 54321},
    "submitStats": {
        "acSubmissionNum": [
            {"difficulty": "All", "count": 120},
            {"difficulty": "Easy", "count": 50},
            {"difficulty": "Medium", "count": 55},
            {"difficulty": "Hard", "count": 15},
        ]
    },
}


# ---------------------------------------------------------------------------
# counts_by_difficulty
# ---------------------------------------------------------------------------


def test_counts_by_difficulty_lowercases_keys():
    counts = counts_by_difficulty(SAMPLE_PROFILE)
    assert counts == {"all": 120, "easy": 50, "medium": 55, "hard": 15}


def test_counts_by_difficulty_handles_missing_stats():
    assert counts_by_difficulty({}) == {}


def test_counts_by_difficulty_defaults_missing_count_to_zero():
    profile = {"submitStats": {"acSubmissionNum": [{"difficulty": "Easy"}]}}
    assert counts_by_difficulty(profile) == {"easy": 0}


# ---------------------------------------------------------------------------
# fetch_leetcode_profile
# ---------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeAsyncClient:
    def __init__(self, payload):
        self._payload = payload
        self.posted = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json):
        self.posted = (url, json)
        return FakeResponse(self._payload)


@pytest.fixture
def patch_client(monkeypatch):
    def _install(payload):
        client = FakeAsyncClient(payload)
        monkeypatch.setattr(leetcode.httpx, "AsyncClient", lambda *a, **k: client)
        return client

    return _install


@pytest.mark.asyncio
async def test_fetch_leetcode_profile_returns_matched_user(patch_client):
    patch_client({"data": {"matchedUser": SAMPLE_PROFILE}})
    result = await fetch_leetcode_profile("ada")
    assert result["username"] == "ada"


@pytest.mark.asyncio
async def test_fetch_leetcode_profile_sends_username_variable(patch_client):
    client = patch_client({"data": {"matchedUser": SAMPLE_PROFILE}})
    await fetch_leetcode_profile("ada")
    assert client.posted[1]["variables"]["username"] == "ada"


@pytest.mark.asyncio
async def test_fetch_leetcode_profile_raises_when_user_missing(patch_client):
    patch_client({"data": {"matchedUser": None}})
    with pytest.raises(ValueError, match="not found"):
        await fetch_leetcode_profile("ghost")


# ---------------------------------------------------------------------------
# sync_leetcode / delete_leetcode_source
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_leetcode_creates_snapshot_and_account(db_session, monkeypatch):
    user = User(id="u1", slug="ada")
    db_session.add(user)
    db_session.commit()

    async def fake_fetch(username):
        return SAMPLE_PROFILE

    monkeypatch.setattr(leetcode, "fetch_leetcode_profile", fake_fetch)

    snapshot = await sync_leetcode(db_session, user, "ada")
    assert snapshot.total_solved == 120
    assert snapshot.medium_solved == 55
    assert snapshot.ranking == 54321

    account = (
        db_session.query(ConnectedAccount)
        .filter(ConnectedAccount.user_id == "u1", ConnectedAccount.kind == SourceKind.leetcode)
        .one()
    )
    assert account.external_username == "ada"
    assert account.last_synced_at is not None


@pytest.mark.asyncio
async def test_sync_leetcode_reuses_existing_account(db_session, monkeypatch):
    user = User(id="u1", slug="ada")
    db_session.add(user)
    db_session.add(ConnectedAccount(user_id="u1", kind=SourceKind.leetcode, external_username="old"))
    db_session.commit()

    async def fake_fetch(username):
        return SAMPLE_PROFILE

    monkeypatch.setattr(leetcode, "fetch_leetcode_profile", fake_fetch)

    await sync_leetcode(db_session, user, "ada")
    accounts = (
        db_session.query(ConnectedAccount)
        .filter(ConnectedAccount.user_id == "u1", ConnectedAccount.kind == SourceKind.leetcode)
        .all()
    )
    assert len(accounts) == 1
    assert accounts[0].external_username == "ada"


def test_delete_leetcode_source_removes_snapshots_and_account(db_session):
    user = User(id="u1", slug="ada")
    db_session.add(user)
    db_session.add(LeetCodeSnapshot(user_id="u1", username="ada", total_solved=10))
    db_session.add(ConnectedAccount(user_id="u1", kind=SourceKind.leetcode, external_username="ada"))
    db_session.commit()

    delete_leetcode_source(db_session, user)

    assert db_session.query(LeetCodeSnapshot).filter_by(user_id="u1").count() == 0
    assert (
        db_session.query(ConnectedAccount)
        .filter(ConnectedAccount.user_id == "u1", ConnectedAccount.kind == SourceKind.leetcode)
        .count()
        == 0
    )
