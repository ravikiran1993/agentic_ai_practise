from __future__ import annotations

from dataclasses import replace
from collections import Counter

from .models import RetrievedEvidence
from .scoring import compute_trend_score


def rerank_evidence(
    evidence_items: list[RetrievedEvidence],
    query: str,
    today: str | None = None,
) -> list[RetrievedEvidence]:
    """Rerank retrieved chunks using semantic relevance plus trend signals."""
    source_counts = Counter(item.source_type for item in evidence_items)
    startup_counts = Counter(item.startup_name for item in evidence_items)
    source_diversity = len(source_counts) / max(len(evidence_items), 1)

    ranked = []
    for item in evidence_items:
        trend = compute_trend_score(
            item,
            query=query,
            today=today,
            source_diversity=source_diversity,
            evidence_count=startup_counts[item.startup_name],
        )
        rerank_score = round((item.similarity_score * 0.55) + ((trend.total / 100) * 0.45), 4)
        ranked.append(replace(item, trend_score=trend.total, rerank_score=rerank_score))
    return sorted(ranked, key=lambda item: item.rerank_score, reverse=True)
