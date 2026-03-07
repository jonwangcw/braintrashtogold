from __future__ import annotations

from datetime import datetime
from pathlib import Path


class DebugLogger:
    def __init__(self, content_id: int, artifacts_dir: Path) -> None:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        self._path = artifacts_dir / "debug_ingest.log"
        with open(self._path, "w", encoding="utf-8") as f:
            f.write(f"=== INGEST DEBUG LOG content_id={content_id} ===\n")
            f.write(f"generated: {datetime.utcnow().isoformat()}Z\n")

    def section(self, title: str, body: str) -> None:
        sep = "=" * 60
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(f"\n{sep}\n{title}\n{sep}\n{body}\n")
