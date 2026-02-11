import httpx

from app.config import settings


async def transcribe_audio(file_path: str) -> str:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required for transcription")
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    data = {"model": "gpt-4o-mini-transcribe"}
    async with httpx.AsyncClient() as client:
        with open(file_path, "rb") as audio_file:
            files = {"file": audio_file}
            response = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers=headers,
                data=data,
                files=files,
                timeout=120,
            )
    response.raise_for_status()
    payload = response.json()
    return payload.get("text", "")
