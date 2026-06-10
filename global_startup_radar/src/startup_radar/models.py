from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StartupEvidence:
    startup_name: str
    source_type: str
    source_name: str
    source_url: str
    title: str
    text: str
    published_at: str | None = None
    topics: list[str] = field(default_factory=list)
    sector: str | None = None
    region: str | None = None
    country: str | None = None
    product_url: str | None = None
    product_hunt_votes: int = 0
    product_hunt_comments: int = 0
    yc_batch: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceChunk:
    id: str
    startup_name: str
    text: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class RetrievedEvidence:
    chunk_id: str
    startup_name: str
    text: str
    source_url: str
    source_type: str
    similarity_score: float
    metadata: dict[str, Any] = field(default_factory=dict)
    rerank_score: float = 0.0
    trend_score: float = 0.0


@dataclass(frozen=True)
class TrendScore:
    total: float
    components: dict[str, float]

