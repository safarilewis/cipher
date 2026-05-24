import base64
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app.models import ConnectedAccount, GitHubRepository, SourceKind, User


GITHUB_API = "https://api.github.com"
COMMIT_PAGE_SIZE = 100
MAX_CODE_FILE_CHARS = 6000
MAX_TREE_PATHS = 100
KEY_FILE_NAMES = {
    "README.md",
    "readme.md",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "Dockerfile",
    "docker-compose.yml",
    "next.config.ts",
    "tsconfig.json",
    "app/main.py",
    "src/main.ts",
    "src/index.ts",
    "src/App.tsx",
}


def parse_github_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


async def fetch_github_repositories(username: str, access_token: str | None = None) -> list[dict]:
    headers = {"Accept": "application/vnd.github+json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            f"{GITHUB_API}/users/{username}/repos",
            params={"sort": "pushed", "per_page": 50},
            headers=headers,
        )
        response.raise_for_status()
        return response.json()


def github_headers(access_token: str | None = None) -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


async def fetch_commit_count(
    client: httpx.AsyncClient,
    full_name: str,
    access_token: str | None = None,
    author: str | None = None,
) -> int:
    total = 0
    page = 1
    while True:
        params: dict[str, str | int] = {
            "per_page": COMMIT_PAGE_SIZE,
            "page": page,
        }
        if author:
            params["author"] = author
        response = await client.get(
            f"{GITHUB_API}/repos/{full_name}/commits",
            params=params,
            headers=github_headers(access_token),
        )
        if response.status_code in {204, 409, 422}:
            return total
        response.raise_for_status()
        commits = response.json()
        total += len(commits)
        if len(commits) < COMMIT_PAGE_SIZE:
            return total
        page += 1


async def fetch_all_time_commit_count(
    client: httpx.AsyncClient,
    full_name: str,
    access_token: str | None = None,
    author: str | None = None,
) -> int:
    return await fetch_commit_count(client, full_name, access_token, author)


async def fetch_commit_counts(
    repos: list[dict],
    access_token: str | None = None,
    author: str | None = None,
) -> dict[str, int]:
    async with httpx.AsyncClient(timeout=20) as client:
        results = await asyncio_gather_limited(
            [lambda repo=repo: fetch_commit_count(client, repo["full_name"], access_token, author) for repo in repos],
            limit=6,
        )
    return {repo["full_name"]: count for repo, count in zip(repos, results, strict=False)}


async def fetch_all_time_commit_counts(
    repos: list[dict],
    access_token: str | None = None,
    author: str | None = None,
) -> dict[str, int]:
    async with httpx.AsyncClient(timeout=20) as client:
        results = await asyncio_gather_limited(
            [lambda repo=repo: fetch_all_time_commit_count(client, repo["full_name"], access_token, author) for repo in repos],
            limit=6,
        )
    return {repo["full_name"]: count for repo, count in zip(repos, results, strict=False)}


async def asyncio_gather_limited(tasks, limit: int) -> list:
    import asyncio

    semaphore = asyncio.Semaphore(limit)

    async def run(task):
        async with semaphore:
            try:
                return await task()
            except httpx.HTTPError:
                return 0

    return await asyncio.gather(*(run(task) for task in tasks))


async def sync_github(db: Session, user: User, username: str, access_token: str | None = None) -> ConnectedAccount:
    repos = await fetch_github_repositories(username, access_token)
    commit_counts = await fetch_commit_counts(repos, access_token, author=username)
    all_time_commit_counts = await fetch_all_time_commit_counts(repos, access_token, author=username)
    account = (
        db.query(ConnectedAccount)
        .filter(ConnectedAccount.user_id == user.id, ConnectedAccount.kind == SourceKind.github)
        .one_or_none()
    )
    if not account:
        account = ConnectedAccount(user_id=user.id, kind=SourceKind.github, external_username=username)
        db.add(account)

    account.external_username = username
    account.access_token = access_token
    account.raw_snapshot = {
        "repository_count": len(repos),
        "total_commit_count": sum(commit_counts.values()),
        "all_time_commit_count": sum(all_time_commit_counts.values()),
        "synced_from": "github",
    }
    account.last_synced_at = datetime.utcnow()

    for repo in repos:
        full_name = repo["full_name"]
        record = (
            db.query(GitHubRepository)
            .filter(GitHubRepository.user_id == user.id, GitHubRepository.full_name == full_name)
            .one_or_none()
        )
        if not record:
            record = GitHubRepository(user_id=user.id, full_name=full_name)
            db.add(record)
        record.description = repo.get("description")
        record.language = repo.get("language")
        record.stars = repo.get("stargazers_count") or 0
        record.forks = repo.get("forks_count") or 0
        record.open_issues = repo.get("open_issues_count") or 0
        record.commit_count = commit_counts.get(full_name, 0)
        record.all_time_commit_count = all_time_commit_counts.get(full_name, 0)
        record.pushed_at = parse_github_datetime(repo.get("pushed_at"))
        record.raw = repo

    db.commit()
    db.refresh(account)
    return account


def get_github_access_token(db: Session, user: User) -> str | None:
    account = (
        db.query(ConnectedAccount)
        .filter(ConnectedAccount.user_id == user.id, ConnectedAccount.kind == SourceKind.github)
        .one_or_none()
    )
    return account.access_token if account else None


def choose_key_paths(paths: list[str]) -> list[str]:
    selected = []
    for path in paths:
        if path in KEY_FILE_NAMES or path.split("/")[-1] in KEY_FILE_NAMES:
            selected.append(path)
    if len(selected) >= 6:
        return selected[:6]

    preferred_prefixes = ("app/", "src/", "backend/app/", "frontend/app/", "lib/", "components/")
    for path in paths:
        if path.endswith((".py", ".ts", ".tsx", ".js")) and path.startswith(preferred_prefixes):
            selected.append(path)
        if len(selected) >= 6:
            break
    return selected[:6]


def decode_github_content(payload: dict) -> str:
    content = payload.get("content") or ""
    encoding = payload.get("encoding")
    if encoding == "base64":
        return base64.b64decode(content).decode("utf-8", errors="replace")
    return str(content)


def fetch_repo_code_context(full_name: str, access_token: str | None = None) -> dict:
    headers = github_headers(access_token)
    with httpx.Client(timeout=25) as client:
        repo_response = client.get(f"{GITHUB_API}/repos/{full_name}", headers=headers)
        repo_response.raise_for_status()
        repo = repo_response.json()
        default_branch = repo.get("default_branch") or "main"

        readme_text = ""
        readme_response = client.get(f"{GITHUB_API}/repos/{full_name}/readme", headers=headers)
        if readme_response.status_code == 200:
            readme_text = decode_github_content(readme_response.json())[:MAX_CODE_FILE_CHARS]

        tree_paths: list[str] = []
        tree_response = client.get(
            f"{GITHUB_API}/repos/{full_name}/git/trees/{default_branch}",
            params={"recursive": "1"},
            headers=headers,
        )
        if tree_response.status_code == 200:
            tree_paths = [
                item["path"]
                for item in tree_response.json().get("tree", [])
                if item.get("type") == "blob"
            ]

        key_files = []
        for path in choose_key_paths(tree_paths):
            content_response = client.get(f"{GITHUB_API}/repos/{full_name}/contents/{path}", headers=headers)
            if content_response.status_code != 200:
                continue
            text = decode_github_content(content_response.json())
            key_files.append({"path": path, "content": text[:MAX_CODE_FILE_CHARS]})

    return {
        "full_name": full_name,
        "default_branch": default_branch,
        "file_count": len(tree_paths),
        "structure_sample": tree_paths[:MAX_TREE_PATHS],
        "readme": readme_text,
        "key_files": key_files,
        "sampling_strategy": (
            "For large repositories, evaluate structure_sample, README, and selected key files. "
            "The included source snippets are the code evidence for review."
        ),
    }


def delete_github_source(db: Session, user: User) -> None:
    db.query(GitHubRepository).filter(GitHubRepository.user_id == user.id).delete()
    db.query(ConnectedAccount).filter(
        ConnectedAccount.user_id == user.id,
        ConnectedAccount.kind == SourceKind.github,
    ).delete()
    db.commit()
