import json

import httpx
import trafilatura


def _format_article_title(title: str | None, author: str | None) -> str | None:
    if not title:
        return None
    if not author or not author.strip():
        return title
    # trafilatura separates multiple authors with "; "
    parts = [p.strip() for p in author.split(";") if p.strip()]
    if len(parts) >= 2:
        return f"{title} - {parts[0]} et al."
    return f"{title} - {parts[0]}"


def extract_webpage_text(url: str) -> tuple[str, str | None]:
    response = httpx.get(url, timeout=30, follow_redirects=True)
    response.raise_for_status()
    html = response.text

    raw = trafilatura.extract(html, output_format="json", include_comments=False)
    if raw:
        try:
            data = json.loads(raw)
            text = data.get("text") or ""
            page_title = data.get("title") or None
            author = data.get("author") or None
            return text, _format_article_title(page_title, author)
        except (json.JSONDecodeError, AttributeError):
            pass

    return trafilatura.extract(html) or "", None
