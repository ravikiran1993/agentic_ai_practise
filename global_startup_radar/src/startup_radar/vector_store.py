from __future__ import annotations

import os

from startup_radar.models import EvidenceChunk, RetrievedEvidence


def create_pinecone_vector_store(index_name: str | None = None):
    """Create a LangChain Pinecone vector store using OpenAI embeddings."""
    try:
        from langchain_openai import OpenAIEmbeddings
        from langchain_pinecone import PineconeVectorStore
    except ImportError as exc:
        raise RuntimeError("Install langchain-openai and langchain-pinecone to use Pinecone search.") from exc

    resolved_index = index_name or os.getenv("PINECONE_INDEX_NAME", "global-startup-radar")
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    return PineconeVectorStore(index_name=resolved_index, embedding=embeddings)


def upsert_chunks(vector_store, chunks: list[EvidenceChunk]) -> None:
    """Upsert chunks into a LangChain-compatible vector store."""
    try:
        from langchain_core.documents import Document
    except ImportError as exc:
        raise RuntimeError("Install langchain-core to upsert documents.") from exc

    documents = [Document(page_content=chunk.text, metadata={**chunk.metadata, "chunk_id": chunk.id}) for chunk in chunks]
    ids = [chunk.id for chunk in chunks]
    vector_store.add_documents(documents, ids=ids)


def search_vector_store(vector_store, query: str, k: int = 20, filters: dict | None = None) -> list[RetrievedEvidence]:
    """Search a LangChain vector store and normalize results."""
    results = vector_store.similarity_search_with_score(query, k=k, filter=filters)
    evidence = []
    for document, score in results:
        metadata = dict(document.metadata)
        evidence.append(
            RetrievedEvidence(
                chunk_id=metadata.get("chunk_id", ""),
                startup_name=metadata.get("startup_name", "Unknown Startup"),
                text=document.page_content,
                source_url=metadata.get("source_url", ""),
                source_type=metadata.get("source_type", "unknown"),
                similarity_score=float(score),
                metadata=metadata,
            )
        )
    return evidence
