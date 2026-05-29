import asyncio
import base64
import logging
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app.models import ConnectedAccount, GitHubRepository, SourceKind, User


GITHUB_API = "https://api.github.com"
COMMIT_PAGE_SIZE = 100
RECENT_COMMIT_LIMIT = 8
MAX_TREE_PATHS = 100
MAX_REVIEW_FILES = 30
MAX_FILE_CONTENT_CHARS = 20000
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

IGNORED_REVIEW_PATH_SEGMENTS = (
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "node_modules",
    ".next",
    "dist",
    "build",
)

IGNORED_REVIEW_FILE_SUFFIXES = (
    ".pyc",
    ".pyo",
    ".class",
    ".o",
    ".so",
    ".dll",
    ".dylib",
)

logger = logging.getLogger(__name__)


def is_committed_env_file(path: str) -> bool:
    lowered = path.lower()
    file_name = lowered.split("/")[-1]
    if file_name.endswith((".example", ".sample", ".template", ".dist")):
        return False
    return (
        file_name == ".env"
        or file_name.startswith(".env.")
        or file_name.startswith("env.")
        or file_name == ".envrc"
    )


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


async def fetch_recent_commits(
    client: httpx.AsyncClient,
    full_name: str,
    access_token: str | None = None,
    author: str | None = None,
    limit: int = RECENT_COMMIT_LIMIT,
) -> list[dict]:
    params: dict[str, str | int] = {"per_page": limit, "page": 1}
    if author:
        params["author"] = author
    response = await client.get(
        f"{GITHUB_API}/repos/{full_name}/commits",
        params=params,
        headers=github_headers(access_token),
    )
    if response.status_code in {204, 409, 422}:
        return []
    response.raise_for_status()
    commits = response.json()
    if not isinstance(commits, list):
        return []
    output = []
    for commit in commits[:limit]:
        commit_data = commit.get("commit") or {}
        author_data = commit_data.get("author") or {}
        message = str(commit_data.get("message") or "").splitlines()[0].strip()
        output.append(
            {
                "sha": str(commit.get("sha") or "")[:12],
                "message": message[:160],
                "authored_at": author_data.get("date"),
                "url": commit.get("html_url"),
            }
        )
    return output


async def fetch_repo_metadata(
    repos: list[dict],
    access_token: str | None = None,
    author: str | None = None,
    concurrency: int = 6,
) -> dict[str, dict]:
    """Fetch commit count + recent commits per repo in a single concurrent pass.

    Replaces three sequential gathers (commit_counts, all_time_commit_counts,
    recent_commit_summaries) — the all_time variant was identical to commit_counts,
    so it's collapsed; the remaining two run concurrently per repo on a shared client.
    """
    if not repos:
        return {}
    semaphore = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(timeout=20) as client:
        async def gather_one(repo):
            full_name = repo["full_name"]
            async with semaphore:
                try:
                    count, recent = await asyncio.gather(
                        fetch_commit_count(client, full_name, access_token, author),
                        fetch_recent_commits(client, full_name, access_token, author),
                    )
                except httpx.HTTPError:
                    return full_name, {"commit_count": 0, "recent_commits": []}
            return full_name, {"commit_count": count, "recent_commits": recent if isinstance(recent, list) else []}
        results = await asyncio.gather(*(gather_one(repo) for repo in repos))
    return dict(results)


async def fetch_all_repo_code_contexts(
    repos: list[dict],
    access_token: str | None = None,
    concurrency: int = 8,
) -> dict[str, dict | None]:
    if not repos:
        return {}
    semaphore = asyncio.Semaphore(concurrency)

    async def run(repo):
        full_name = repo["full_name"]
        async with semaphore:
            try:
                context = await asyncio.to_thread(fetch_repo_code_context, full_name, access_token)
                return full_name, context
            except Exception as exc:
                logger.warning("Code context sync failed for %s: %s", full_name, exc)
                return full_name, None

    results = await asyncio.gather(*(run(repo) for repo in repos))
    return dict(results)


async def sync_github(db: Session, user: User, username: str, access_token: str | None = None) -> ConnectedAccount:
    repos = await fetch_github_repositories(username, access_token)
    metadata, code_contexts = await asyncio.gather(
        fetch_repo_metadata(repos, access_token, author=username),
        fetch_all_repo_code_contexts(repos, access_token),
    )

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
    total_commit_count = sum(meta["commit_count"] for meta in metadata.values())
    account.raw_snapshot = {
        "repository_count": len(repos),
        "total_commit_count": total_commit_count,
        "all_time_commit_count": total_commit_count,
        "recent_commit_count": sum(len(meta["recent_commits"]) for meta in metadata.values()),
        "synced_from": "github",
    }
    account.last_synced_at = datetime.utcnow()

    existing_records = {
        record.full_name: record
        for record in db.query(GitHubRepository).filter(GitHubRepository.user_id == user.id).all()
    }
    for repo in repos:
        full_name = repo["full_name"]
        record = existing_records.get(full_name)
        if not record:
            record = GitHubRepository(user_id=user.id, full_name=full_name)
            db.add(record)
        meta = metadata.get(full_name, {"commit_count": 0, "recent_commits": []})
        record.description = repo.get("description")
        record.language = repo.get("language")
        record.stars = repo.get("stargazers_count") or 0
        record.forks = repo.get("forks_count") or 0
        record.open_issues = repo.get("open_issues_count") or 0
        record.commit_count = meta["commit_count"]
        record.all_time_commit_count = meta["commit_count"]
        record.pushed_at = parse_github_datetime(repo.get("pushed_at"))
        record.raw = {**repo, "recent_commits": meta["recent_commits"]}
        context = code_contexts.get(full_name)
        if context is not None:
            record.code_analysis_snapshot = context

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
    selected: list[str] = []
    seen: set[str] = set()

    def add(path: str) -> None:
        if path not in seen and len(selected) < MAX_REVIEW_FILES:
            selected.append(path)
            seen.add(path)

    for path in paths:
        if is_review_noise_path(path):
            continue
        if path in KEY_FILE_NAMES or path.split("/")[-1] in KEY_FILE_NAMES:
            add(path)

    priority_patterns = (
        "/api/",
        "/routes/",
        "/services/",
        "/models/",
        "/schemas",
        "/components/",
        "/hooks/",
        "/lib/",
        "/utils/",
        "/tests/",
        "/test_",
        ".test.",
        ".spec.",
        "docker",
        "compose",
        "migration",
        "alembic",
    )
    preferred_prefixes = ("app/", "src/", "backend/app/", "frontend/app/", "lib/", "components/", "pages/", "server/", "tests/")
    for path in paths:
        if is_review_noise_path(path):
            continue
        normalized = f"/{path.lower()}"
        if path.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java")) and (
            path.startswith(preferred_prefixes) or any(pattern in normalized for pattern in priority_patterns)
        ):
            add(path)

    source_suffixes = (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".cs", ".rb", ".php")
    for path in paths:
        if is_review_noise_path(path):
            continue
        if path.endswith(source_suffixes):
            add(path)

    return selected


def is_review_noise_path(path: str) -> bool:
    lowered = path.lower()
    if any(segment in lowered for segment in IGNORED_REVIEW_PATH_SEGMENTS):
        return True
    return lowered.endswith(IGNORED_REVIEW_FILE_SUFFIXES)


def filter_review_paths(paths: list[str]) -> list[str]:
    return [path for path in paths if not is_review_noise_path(path)]


def decode_github_content(payload: dict) -> str:
    content = payload.get("content") or ""
    encoding = payload.get("encoding")
    if encoding == "base64":
        return base64.b64decode(content).decode("utf-8", errors="replace")
    return str(content)


def fetch_blob_content(client: httpx.Client, blob_url: str | None, headers: dict[str, str]) -> str:
    if not blob_url:
        return ""
    blob_response = client.get(blob_url, headers=headers)
    if blob_response.status_code != 200:
        return ""
    return decode_github_content(blob_response.json())


def fetch_content_text(client: httpx.Client, url: str, headers: dict[str, str]) -> str:
    response = client.get(url, headers=headers)
    if response.status_code != 200:
        return ""

    payload = response.json()
    if isinstance(payload, list):
        return ""

    text = decode_github_content(payload)
    if payload.get("truncated") and payload.get("git_url"):
        blob_text = fetch_blob_content(client, payload.get("git_url"), headers)
        if blob_text:
            return blob_text[:MAX_FILE_CONTENT_CHARS]

    if text:
        return text[:MAX_FILE_CONTENT_CHARS]

    download_url = payload.get("download_url")
    if download_url:
        raw_response = client.get(str(download_url), headers=headers)
        if raw_response.status_code == 200:
            return raw_response.text[:MAX_FILE_CONTENT_CHARS]
    return ""


def fetch_repo_code_context(full_name: str, access_token: str | None = None) -> dict:
    headers = github_headers(access_token)
    with httpx.Client(timeout=35) as client:
        repo_response = client.get(f"{GITHUB_API}/repos/{full_name}", headers=headers)
        repo_response.raise_for_status()
        repo = repo_response.json()
        default_branch = repo.get("default_branch") or "main"

        readme_text = fetch_content_text(client, f"{GITHUB_API}/repos/{full_name}/readme", headers)

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

        review_paths = filter_review_paths(tree_paths)
        committed_env_files = [path for path in tree_paths if is_committed_env_file(path)]

        key_files = []
        for path in choose_key_paths(review_paths):
            text = fetch_content_text(client, f"{GITHUB_API}/repos/{full_name}/contents/{path}", headers)
            if text:
                key_files.append({"path": path, "content": text})

    return {
        "full_name": full_name,
        "default_branch": default_branch,
        "file_count": len(review_paths),
        "ignored_file_count": len(tree_paths) - len(review_paths),
        "committed_env_files": committed_env_files,
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
