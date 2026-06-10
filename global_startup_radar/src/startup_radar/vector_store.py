from __future__ import annotations

import os

from startup_radar.models import EvidenceChunk, RetrievedEvidence


def create_pinecone_vector_store(index_name: str | None = None):
    """Create a LangChain Pinecone vector store using Gemini embeddings."""
    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        from langchain_pinecone import PineconeVectorStore
    except ImportError as exc:
        raise RuntimeError("Install langchain-google-genai and langchain-pinecone to use Pinecone search.") from exc

    resolved_index = index_name or os.getenv("PINECONE_INDEX_NAME", "global-startup-radar")
    embedding_model = os.getenv("GEMINI_EMBEDDING_MODEL", "models/gemini-embedding-001")
    embedding_dimension = int(os.getenv("GEMINI_EMBEDDING_DIMENSION", "1024"))
    embeddings = GoogleGenerativeAIEmbeddings(model=embedding_model, output_dimensionality=embedding_dimension)
    return PineconeVectorStore(index_name=resolved_index, embedding=embeddings)


def upsert_chunks(vector_store, chunks: list[EvidenceChunk]) -> None:
    """Upsert chunks into a LangChain-compatible vector store."""
    try:
        from langchain_core.documents import Document
    except ImportError as exc:
        raise RuntimeError("Install langchain-core to upsert documents.") from exc

    documents = [
        Document(page_content=chunk.text, metadata=sanitize_metadata({**chunk.metadata, "chunk_id": chunk.id}))
        for chunk in chunks
    ]
    ids = [chunk.id for chunk in chunks]
    vector_store.add_documents(documents, ids=ids)


def sanitize_metadata(metadata: dict) -> dict:
    """Return metadata compatible with Pinecone's scalar/list constraints."""
    cleaned = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            cleaned[key] = value
            continue
        if isinstance(value, list):
            string_values = [item for item in value if isinstance(item, str)]
            if string_values:
                cleaned[key] = string_values
    return cleaned


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
