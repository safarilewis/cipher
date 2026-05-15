from app.models import GitHubRepository, LeetCodeSnapshot, ProfileSection


def github_quality_signals(repositories: list[GitHubRepository]) -> dict:
    languages = sorted({repo.language for repo in repositories if repo.language})
    stars = sum(repo.stars for repo in repositories)
    forks = sum(repo.forks for repo in repositories)
    commits = sum(getattr(repo, "commit_count", 0) or 0 for repo in repositories)
    active_projects = sum(1 for repo in repositories if repo.pushed_at)
    complexity = "emerging"
    if len(repositories) >= 8 or stars >= 50 or len(languages) >= 5:
        complexity = "advanced"
    elif len(repositories) >= 3 or stars >= 10 or len(languages) >= 3:
        complexity = "solid"

    return {
        "repository_count": len(repositories),
        "language_count": len(languages),
        "languages": languages,
        "stars": stars,
        "forks": forks,
        "commits": commits,
        "active_projects": active_projects,
        "project_complexity": complexity,
    }


def leetcode_signals(snapshot: LeetCodeSnapshot | None) -> dict:
    if not snapshot:
        return {"available": False}
    return {
        "available": True,
        "total_solved": snapshot.total_solved,
        "easy_solved": snapshot.easy_solved,
        "medium_solved": snapshot.medium_solved,
        "hard_solved": snapshot.hard_solved,
        "ranking": snapshot.ranking,
    }


def profile_signals(sections: list[ProfileSection]) -> dict:
    counts: dict[str, int] = {}
    for section in sections:
        counts[section.kind] = counts.get(section.kind, 0) + 1
    return {"section_counts": counts, "total_sections": len(sections)}
