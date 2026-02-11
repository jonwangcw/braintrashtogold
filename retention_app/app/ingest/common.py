from urllib.parse import urlparse


def validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("URL must start with http or https")


def is_youtube_url(url: str) -> bool:
    host = (urlparse(url).netloc or "").lower()
    return any(domain in host for domain in ("youtube.com", "youtu.be"))
