from __future__ import annotations

from startup_radar.chunking import chunk_evidence_record
from startup_radar.ingestion.product_hunt import fetch_recent_product_hunt_posts, product_hunt_post_to_evidence
from startup_radar.models import RetrievedEvidence


def load_product_hunt_evidence(first: int = 25, posted_after: str | None = None) -> list[RetrievedEvidence]:
    """Fetch recent Product Hunt posts and convert them into retrieved evidence records."""
    posts = fetch_recent_product_hunt_posts(first=first, posted_after=posted_after)
    evidence = []
    for post in posts:
        record = product_hunt_post_to_evidence(post)
        chunk = chunk_evidence_record(record)[0]
        evidence.append(
            RetrievedEvidence(
                chunk_id=chunk.id,
                startup_name=record.startup_name,
                text=chunk.text,
                source_url=record.source_url,
                source_type=record.source_type,
                similarity_score=0.72,
                metadata=chunk.metadata,
            )
        )
    return evidence
