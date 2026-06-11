from __future__ import annotations

from startup_radar.chunking import chunk_evidence_record
from startup_radar.ingestion.company_site import fetch_company_site_to_evidence
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


def enrich_with_company_sites(evidence_items: list[RetrievedEvidence], limit: int = 5) -> list[RetrievedEvidence]:
    """Append company website evidence for Product Hunt items with product URLs."""
    enriched = list(evidence_items)
    seen_urls = set()
    for item in evidence_items:
        if len(seen_urls) >= limit:
            break
        product_url = item.metadata.get("product_url")
        if not product_url or product_url in seen_urls:
            continue
        try:
            record = fetch_company_site_to_evidence(
                startup_name=item.startup_name,
                url=product_url,
                sector=item.metadata.get("sector"),
                region=item.metadata.get("region"),
                country=item.metadata.get("country"),
            )
        except Exception:
            continue
        chunk = chunk_evidence_record(record)[0]
        enriched.append(
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
        seen_urls.add(product_url)
    return enriched
