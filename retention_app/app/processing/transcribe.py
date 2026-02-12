import asyncio
from functools import lru_cache

from app.config import settings


def _load_whisper_model(model_name: str):
    try:
        import whisper
    except ImportError as exc:
        raise ValueError(
            "Local Whisper dependency is missing. Install with `pip install openai-whisper`."
        ) from exc

    return whisper.load_model(model_name)


@lru_cache(maxsize=1)
def _get_model():
    return _load_whisper_model(settings.whisper_model)


def _transcribe_audio_sync(file_path: str) -> str:
    model = _get_model()
    result = model.transcribe(file_path)
    return (result.get("text") or "").strip()


async def transcribe_audio(file_path: str) -> str:
    return await asyncio.to_thread(_transcribe_audio_sync, file_path)
