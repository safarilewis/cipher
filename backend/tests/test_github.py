import pytest

from app.services.github import fetch_all_time_commit_count, fetch_commit_count, filter_review_paths, is_committed_env_file


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
async def test_fetch_all_time_commit_count_matches_default_behavior():
    client = FakeClient()

    count = await fetch_all_time_commit_count(client, "ada/app", author="ada")

    assert count == 137
    assert "since" not in client.calls[0]["params"]


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


def test_is_committed_env_file_identifies_sensitive_env_paths():
    assert is_committed_env_file(".env")
    assert is_committed_env_file("frontend/.env.local")
    assert is_committed_env_file("backend/.env.production")
    assert is_committed_env_file("config/env.dev")
    assert not is_committed_env_file(".env.example")
    assert not is_committed_env_file("README.md")
