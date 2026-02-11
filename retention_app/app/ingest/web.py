import httpx
import trafilatura


def extract_webpage_text(url: str) -> str:
    response = httpx.get(url, timeout=30)
    response.raise_for_status()
    downloaded = trafilatura.extract(response.text)
    return downloaded or ""
