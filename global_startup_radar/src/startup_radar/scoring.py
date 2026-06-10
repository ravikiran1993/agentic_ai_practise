from __future__ import annotations

from datetime import date, datetime
from math import log10

from .models import RetrievedEvidence, TrendScore


def compute_trend_score(
    evidence: RetrievedEvidence,
    query: str,
    today: str | None = None,
    source_diversity: float = 0.0,
    evidence_count: int = 1,
) -> TrendScore:
    """Return an explainable 0-100 trend score for one evidence item."""
    metadata = evidence.metadata
    components = {
        "semantic_relevance": _clamp(evidence.similarity_score),
        "launch_recency": _recency_score(metadata.get("published_at"), today),
        "product_hunt_votes": _log_scale(metadata.get("product_hunt_votes", 0), cap=1000),
        "product_hunt_comments": _log_scale(metadata.get("product_hunt_comments", 0), cap=200),
        "source_diversity": _clamp(source_diversity),
        "evidence_count": _clamp(evidence_count / 5),
        "sector_or_region_match": _query_match(query, metadata),
    }
    weights = {
        "semantic_relevance": 0.30,
        "launch_recency": 0.18,
        "product_hunt_votes": 0.14,
        "product_hunt_comments": 0.10,
        "source_diversity": 0.10,
        "evidence_count": 0.08,
        "sector_or_region_match": 0.10,
    }
    total = sum(components[name] * weights[name] for name in weights) * 100
    return TrendScore(total=round(_clamp(total, 0, 100), 2), components=components)


def _recency_score(value: str | None, today: str | None) -> float:
    if not value:
        return 0.0
    try:
        item_date = datetime.fromisoformat(value[:10]).date()
        current = datetime.fromisoformat(today[:10]).date() if today else date.today()
    except ValueError:
        return 0.0
    age_days = max((current - item_date).days, 0)
    if age_days <= 7:
        return 1.0
    if age_days >= 180:
        return 0.0
    return round(1 - (age_days / 180), 4)


def _log_scale(value: object, cap: int) -> float:
    try:
        numeric = max(float(value), 0.0)
    except (TypeError, ValueError):
        numeric = 0.0
    return _clamp(log10(numeric + 1) / log10(cap + 1))


def _query_match(query: str, metadata: dict) -> float:
    haystack = " ".join(
        str(value)
        for value in [
            metadata.get("sector"),
            metadata.get("region"),
            metadata.get("country"),
            " ".join(metadata.get("topics") or []),
        ]
        if value
    ).lower()
    query_terms = {term.strip().lower() for term in query.replace(",", " ").split() if len(term) > 2}
    if not haystack or not query_terms:
        return 0.0
    matches = sum(1 for term in query_terms if term in haystack)
    return _clamp(matches / min(len(query_terms), 4))


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))

