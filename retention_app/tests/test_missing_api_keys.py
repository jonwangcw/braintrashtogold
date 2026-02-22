import pytest

from app.llm.openrouter_client import OpenRouterClient


def test_openrouter_client_requires_api_key(monkeypatch):
    monkeypatch.setattr("app.llm.openrouter_client.settings.openrouter_api_key", "")
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        OpenRouterClient()
