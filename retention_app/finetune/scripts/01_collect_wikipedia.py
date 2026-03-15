"""
01_collect_wikipedia.py — Download Wikipedia articles by title.

Reads data/raw/wikipedia_topics.txt (one title per line), fetches each article
via the Wikipedia REST API (no authentication required), and writes the results
to data/raw/wikipedia_articles.json.

Usage:
    python scripts/01_collect_wikipedia.py
"""

import json
import urllib.parse
import urllib.request
from pathlib import Path


_WIKI_API = "https://en.wikipedia.org/w/api.php"


def fetch_article(title: str) -> dict | None:
    """Fetch the full plain-text content of a Wikipedia article by title."""
    params = urllib.parse.urlencode({
        "action": "query",
        "titles": title,
        "prop": "extracts",
        "explaintext": True,
        "exsectionformat": "plain",
        "redirects": True,
        "format": "json",
    })
    url = f"{_WIKI_API}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "braintrashtogold-finetune/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    pages = data["query"]["pages"]
    page = next(iter(pages.values()))

    if "missing" in page:
        return None

    return {"title": page["title"], "text": page.get("extract", "")}


def main() -> None:
    base = Path(__file__).parent.parent
    topics_file = base / "data" / "raw" / "wikipedia_topics.txt"
    out_file = base / "data" / "raw" / "wikipedia_articles.json"

    if not topics_file.exists():
        print(f"No topics file found at {topics_file}. Create it with one title per line.")
        return

    titles = [
        line.strip()
        for line in topics_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    print(f"Fetching {len(titles)} Wikipedia articles...")

    curated: list[dict] = []
    for title in titles:
        try:
            article = fetch_article(title)
            if article:
                curated.append(article)
                print(f"  OK:      {article['title']}  ({len(article['text'])} chars)")
            else:
                print(f"  MISSING: {title}")
        except Exception as exc:
            print(f"  ERROR:   {title} — {exc}")

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(curated, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {len(curated)} articles to {out_file}")


if __name__ == "__main__":
    main()