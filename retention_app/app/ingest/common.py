from urllib.parse import urlparse


def validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("URL must start with http or https")


def is_youtube_url(url: str) -> bool:
    host = (urlparse(url).netloc or "").lower()
    return any(domain in host for domain in ("youtube.com", "youtu.be"))


def detect_source_type(url: str) -> str:
    parsed = urlparse(url)
    path = (parsed.path or "").lower()

    if is_youtube_url(url):
        return "youtube"

    if path.endswith(".pdf"):
        return "pdf"

    if path.endswith((".xml", ".rss")) or "feed" in path:
        return "rss_episode"

    return "webpage"
