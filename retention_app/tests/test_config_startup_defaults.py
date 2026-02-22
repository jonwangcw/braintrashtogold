from app.config import settings


def test_settings_load_with_defaults():
    assert settings.openrouter_model
