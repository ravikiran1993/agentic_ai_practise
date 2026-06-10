from __future__ import annotations

import hashlib

from .models import EvidenceChunk, StartupEvidence


def chunk_evidence_record(record: StartupEvidence) -> list[EvidenceChunk]:
    """Create a source-aware chunk from one normalized evidence record."""
    text_parts = [
        f"Startup: {record.startup_name}",
        f"Source: {record.source_name} ({record.source_type})",
        f"Title: {record.title}",
        f"Summary: {record.text}",
    ]
    if record.topics:
        text_parts.append(f"Topics: {', '.join(record.topics)}")
    if record.sector:
        text_parts.append(f"Sector: {record.sector}")
    if record.region or record.country:
        location = ", ".join(part for part in [record.region, record.country] if part)
        text_parts.append(f"Location: {location}")
    if record.published_at:
        text_parts.append(f"Published: {record.published_at}")

    chunk_text = "\n".join(text_parts)
    chunk_id = _stable_chunk_id(record.source_url, record.startup_name, record.title)
    metadata = {
        **record.metadata,
        "startup_name": record.startup_name,
        "source_type": record.source_type,
        "source_name": record.source_name,
        "source_url": record.source_url,
        "title": record.title,
        "published_at": record.published_at,
        "topics": record.topics,
        "sector": record.sector,
        "region": record.region,
        "country": record.country,
        "product_url": record.product_url,
        "product_hunt_votes": record.product_hunt_votes,
        "product_hunt_comments": record.product_hunt_comments,
        "yc_batch": record.yc_batch,
    }
    return [EvidenceChunk(id=chunk_id, startup_name=record.startup_name, text=chunk_text, metadata=metadata)]


def _stable_chunk_id(*parts: str) -> str:
    raw = "|".join(parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"chunk-{digest}"

