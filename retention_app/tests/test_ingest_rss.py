import asyncio

import pytest

from app.ingest.rss import ingest_rss


def test_ingest_rss_not_implemented():
    with pytest.raises(NotImplementedError):
        asyncio.run(ingest_rss("https://example.com/feed", "https://example.com/episode"))
