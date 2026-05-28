import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import GitHubRepository, User
from app.services.github import choose_key_paths, fetch_commit_count, fetch_recent_commits, filter_review_paths, is_committed_env_file
from app.services.github import sync_github


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.headers = {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class FakeClient:
    def __init__(self):
        self.calls = []

    async def get(self, url, params=None, headers=None):
        self.calls.append({"url": url, "params": params, "headers": headers})
        if params is None:
            return FakeResponse([])
        if params["page"] == 1:
            return FakeResponse([{}] * 100)
        if params["page"] == 2:
            return FakeResponse([{}] * 37)
        return FakeResponse([])


@pytest.mark.asyncio
async def test_fetch_commit_count_paginates_and_filters_by_author():
    client = FakeClient()

    count = await fetch_commit_count(client, "ada/app", author="ada")

    assert count == 137
    assert client.calls[0]["params"]["author"] == "ada"
    assert client.calls[0]["params"]["per_page"] == 100
    assert client.calls[1]["params"]["page"] == 2
    assert "since" not in client.calls[0]["params"]


@pytest.mark.asyncio
async def test_fetch_recent_commits_returns_lightweight_change_summaries():
    class RecentCommitClient:
        async def get(self, url, params=None, headers=None):
            assert params["per_page"] == 8
            return FakeResponse(
                [
                    {
                        "sha": "abcdef1234567890",
                        "html_url": "https://github.com/ada/app/commit/abcdef",
                        "commit": {
                            "message": "Add billing flow\n\nLonger body",
                            "author": {"date": "2026-05-01T00:00:00Z"},
                        },
                    }
                ]
            )

    commits = await fetch_recent_commits(RecentCommitClient(), "ada/app", author="ada")

    assert commits == [
        {
            "sha": "abcdef123456",
            "message": "Add billing flow",
            "authored_at": "2026-05-01T00:00:00Z",
            "url": "https://github.com/ada/app/commit/abcdef",
        }
    ]


def test_filter_review_paths_ignores_generated_and_cache_files():
    paths = [
        "src/app.py",
        "src/__pycache__/app.cpython-312.pyc",
        "node_modules/react/index.js",
        "build/output.js",
        "dist/app.js",
        "README.md",
    ]

    filtered = filter_review_paths(paths)

    assert filtered == ["src/app.py", "README.md"]


def test_choose_key_paths_samples_more_representative_files():
    paths = [
        "README.md",
        "package.json",
        "src/index.ts",
        "src/api/users.ts",
        "src/services/billing.ts",
        "src/models/user.ts",
        "src/components/Profile.tsx",
        "src/hooks/useProfile.ts",
        "src/lib/auth.ts",
        "src/utils/date.ts",
        "tests/profile.test.ts",
        "node_modules/react/index.js",
        "dist/bundle.js",
        *[f"src/features/feature{i}.ts" for i in range(40)],
    ]

    selected = choose_key_paths(paths)

    assert len(selected) == 30
    assert "README.md" in selected
    assert "src/services/billing.ts" in selected
    assert "tests/profile.test.ts" in selected
    assert "node_modules/react/index.js" not in selected
    assert "dist/bundle.js" not in selected


def test_is_committed_env_file_identifies_sensitive_env_paths():
    assert is_committed_env_file(".env")
    assert is_committed_env_file("frontend/.env.local")
    assert is_committed_env_file("backend/.env.production")
    assert is_committed_env_file("config/env.dev")
    assert not is_committed_env_file(".env.example")
    assert not is_committed_env_file("README.md")


@pytest.mark.asyncio
async def test_sync_github_chunks_and_embeds_code_context_during_connection(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    user = User(id="user-1", email="user@example.com", name="Ada", slug="ada")
    db.add(user)
    db.commit()

    async def fake_fetch_github_repositories(username, access_token=None):
        return [{"full_name": "ada/app", "description": "App", "language": "Python", "stargazers_count": 1, "forks_count": 0, "open_issues_count": 0, "pushed_at": "2026-05-01T00:00:00Z"}]

    async def fake_fetch_repo_metadata(repos, access_token=None, author=None, concurrency=6):
        return {
            "ada/app": {
                "commit_count": 7,
                "recent_commits": [
                    {"sha": "abc123", "message": "Add profile editor", "authored_at": "2026-05-01T00:00:00Z", "url": None}
                ],
            }
        }

    def fake_fetch_repo_code_context(full_name, access_token=None):
        return {
            "full_name": full_name,
            "readme": "line1\nline2\nline3",
            "structure_sample": ["src/app.py"],
            "key_files": [{"path": "src/app.py", "content": "a\nb\nc\nd"}],
        }

    monkeypatch.setattr("app.services.github.fetch_github_repositories", fake_fetch_github_repositories)
    monkeypatch.setattr("app.services.github.fetch_repo_metadata", fake_fetch_repo_metadata)
    monkeypatch.setattr("app.services.github.fetch_repo_code_context", fake_fetch_repo_code_context)

    await sync_github(db, user, "ada")

    repo = db.query(GitHubRepository).one()
    assert repo.code_analysis_snapshot["full_name"] == "ada/app"
    assert repo.raw["recent_commits"][0]["message"] == "Add profile editor"
    assert repo.commit_count == 7
    assert repo.all_time_commit_count == 7
