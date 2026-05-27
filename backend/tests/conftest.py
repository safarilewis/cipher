import pytest
from types import SimpleNamespace

import os

from app.core.config import get_settings


class DummySettings:
    openai_api_key = None
    anthropic_api_key = None


@pytest.fixture(autouse=True)
def disable_external_api_calls(monkeypatch):
    """Disable real OpenAI/Anthropic calls during tests by patching get_settings."""
    monkeypatch.setattr("app.services.analysis.get_settings", lambda: DummySettings())
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    yield
