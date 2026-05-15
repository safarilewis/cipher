from app.services.scoring import github_quality_signals, leetcode_signals, profile_signals
from app.services.refresh_policy import free_tier_refresh_days, next_free_tier_refresh_at, assert_free_tier_refresh_allowed
from datetime import datetime, timedelta
from fastapi import HTTPException
import pytest


class Repo:
    def __init__(self, language="Python", stars=0, forks=0, pushed_at=True, commit_count=0):
        self.language = language
        self.stars = stars
        self.forks = forks
        self.pushed_at = pushed_at
        self.commit_count = commit_count


class Section:
    def __init__(self, kind):
        self.kind = kind


class Snapshot:
    total_solved = 42
    easy_solved = 20
    medium_solved = 17
    hard_solved = 5
    ranking = 123456


def test_github_quality_signals_scores_project_complexity():
    repos = [Repo("Python", 20, commit_count=12), Repo("TypeScript", 0, commit_count=5), Repo("Go", 0)]
    signals = github_quality_signals(repos)
    assert signals["project_complexity"] == "solid"
    assert signals["language_count"] == 3
    assert signals["stars"] == 20
    assert signals["commits"] == 17


def test_leetcode_signals_handles_missing_snapshot():
    assert leetcode_signals(None) == {"available": False}
    assert leetcode_signals(Snapshot())["total_solved"] == 42


def test_profile_signals_counts_sections_by_kind():
    signals = profile_signals([Section("education"), Section("education"), Section("project")])
    assert signals["total_sections"] == 3
    assert signals["section_counts"]["education"] == 2


class Account:
    def __init__(self, last_synced_at):
        self.last_synced_at = last_synced_at


def test_free_tier_refresh_allows_first_or_older_than_14_days():
    assert_free_tier_refresh_allowed(None)
    assert_free_tier_refresh_allowed(Account(datetime.utcnow() - timedelta(days=free_tier_refresh_days(), minutes=1)))


def test_free_tier_refresh_blocks_before_14_days():
    with pytest.raises(HTTPException):
        assert_free_tier_refresh_allowed(Account(datetime.utcnow() - timedelta(days=2)))


def test_next_free_tier_refresh_date_is_14_days_after_sync():
    synced_at = datetime(2026, 5, 1, 12, 0, 0)
    assert next_free_tier_refresh_at(Account(synced_at)) == datetime(2026, 5, 15, 12, 0, 0)
