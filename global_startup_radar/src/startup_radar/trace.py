from __future__ import annotations

from startup_radar.models import RetrievedEvidence


def build_rag_trace(
    query: str,
    source_chunks: list[RetrievedEvidence],
    pinecone_results: list[RetrievedEvidence],
    reranked: list[RetrievedEvidence],
    final_prompt: str,
    pinecone_filter: dict | None = None,
    pinecone_top_k: int | None = None,
) -> dict:
    """Build an inspectable trace of one RAG chat turn."""
    return {
        "query": query,
        "source_chunks": [_evidence_to_trace_item(item, index) for index, item in enumerate(source_chunks, start=1)],
        "pinecone_query": {
            "input_text": query,
            "top_k": pinecone_top_k,
            "filter": pinecone_filter,
            "embedding_model": "models/gemini-embedding-001",
            "embedding_dimension": 1024,
        },
        "pinecone_results_before_rerank": [
            _evidence_to_trace_item(item, index) for index, item in enumerate(pinecone_results, start=1)
        ],
        "reranked_chunks": [_evidence_to_trace_item(item, index) for index, item in enumerate(reranked, start=1)],
        "llm_prompt": final_prompt,
    }


def _evidence_to_trace_item(item: RetrievedEvidence, position: int) -> dict:
    return {
        "position": position,
        "chunk_id": item.chunk_id,
        "startup_name": item.startup_name,
        "source_type": item.source_type,
        "source_url": item.source_url,
        "similarity_score": round(item.similarity_score, 4),
        "trend_score": round(item.trend_score, 2),
        "rerank_score": round(item.rerank_score, 4),
        "embedding_note": "This chunk is represented as a dense vector in Pinecone when live indexing is enabled.",
        "text": item.text,
        "metadata": item.metadata,
    }
