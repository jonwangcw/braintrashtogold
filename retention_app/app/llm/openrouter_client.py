import httpx

from app.config import settings


class OpenRouterClient:
    def __init__(self) -> None:
        self.api_key = settings.openrouter_api_key
        self.model = settings.openrouter_model

    async def complete(self, prompt: str) -> str:
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
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=120,
            )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
