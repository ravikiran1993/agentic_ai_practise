from __future__ import annotations

import json
from pathlib import Path

from startup_radar.models import StartupEvidence


def load_sample_records(path: str | Path) -> list[StartupEvidence]:
    """Load demo evidence records from a local JSON file."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return [StartupEvidence(**item) for item in payload]

