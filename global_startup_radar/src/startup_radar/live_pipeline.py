from __future__ import annotations

from startup_radar.models import EvidenceChunk, RetrievedEvidence
from startup_radar.vector_store import search_vector_store, upsert_chunks


def evidence_to_chunks(evidence_items: list[RetrievedEvidence]) -> list[EvidenceChunk]:
    """Convert retrieved evidence records back into vector-store chunks."""
    return [
        EvidenceChunk(
            id=item.chunk_id,
            startup_name=item.startup_name,
            text=item.text,
            metadata={
                **item.metadata,
                "chunk_id": item.chunk_id,
                "startup_name": item.startup_name,
                "source_url": item.source_url,
                "source_type": item.source_type,
            },
        )
        for item in evidence_items
    ]


def index_evidence(vector_store, evidence_items: list[RetrievedEvidence]) -> int:
    """Embed and upsert evidence chunks into Pinecone."""
    chunks = evidence_to_chunks(evidence_items)
    if chunks:
        upsert_chunks(vector_store, chunks)
    return len(chunks)


def search_indexed_evidence(
    vector_store,
    query: str,
    k: int = 20,
    metadata_filter: dict | None = None,
) -> list[RetrievedEvidence]:
    """Retrieve semantically relevant evidence from Pinecone."""
    return search_vector_store(vector_store, query, k=k, filters=metadata_filter)


def build_pinecone_filter(
    sources: list[str] | None = None,
    sectors: list[str] | None = None,
    regions: list[str] | None = None,
) -> dict | None:
    """Build a Pinecone metadata filter from selected dashboard filters."""
    metadata_filter = {}
    if sources:
        metadata_filter["source_type"] = {"$in": sources}
    if sectors:
        metadata_filter["sector"] = {"$in": sectors}
    if regions:
        metadata_filter["region"] = {"$in": regions}
    return metadata_filter or None
