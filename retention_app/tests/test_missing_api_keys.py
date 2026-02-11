import asyncio
import pytest

from app.llm.openrouter_client import OpenRouterClient
from app.processing import transcribe as transcribe_module


def test_openrouter_client_requires_api_key(monkeypatch):
    monkeypatch.setattr("app.llm.openrouter_client.settings.openrouter_api_key", "")
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        OpenRouterClient()


def test_transcribe_requires_api_key(monkeypatch):
    monkeypatch.setattr(transcribe_module.settings, "openai_api_key", "")
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        asyncio.run(transcribe_module.transcribe_audio("file.mp3"))
