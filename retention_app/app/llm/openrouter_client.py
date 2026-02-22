import asyncio

import httpx

from app.config import settings


class OpenRouterClient:
    def __init__(self) -> None:
        self.api_key = settings.openrouter_api_key
        self.model = settings.openrouter_model
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY is required for question generation")

    def _complete_sync(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }
        with httpx.Client(timeout=120) as client:
            response = client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
            )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def complete(self, prompt: str) -> str:
        return await asyncio.to_thread(self._complete_sync, prompt)
