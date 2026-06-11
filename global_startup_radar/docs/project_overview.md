# Global Startup Radar: Project Overview

## Executive Summary

Global Startup Radar is a Streamlit-based RAG application for discovering and explaining emerging startups across global markets. It combines live startup launch data, selected company website evidence, Gemini embeddings, Pinecone vector retrieval, explainable reranking, and Gemini answer generation.

The project is designed as more than a chatbot. It exposes the full retrieval-augmented generation pipeline so a reviewer can see what data was collected, how it was chunked, how it was embedded, how Pinecone retrieved evidence, how reranking changed the order, and what exact prompt was sent to the LLM.

## Project Goal

The goal is to help users ask questions such as:

- Which global AI startups are trending and why?
- What climate tech startups are emerging in Europe?
- Which developer tool startups show strong launch traction?
- What evidence supports each startup recommendation?

The answer should be evidence-backed, cited, transparent, and careful about uncertainty.

## High-Level System View

The system follows this flow:

```text
Product Hunt API + company websites
-> normalized startup evidence
-> source-aware chunks
-> Gemini embeddings
-> Pinecone vector index
-> semantic retrieval
-> explainable reranking
-> cited Gemini prompt
-> Streamlit chat answer and RAG trace
```

## Main Data Sources

### Product Hunt API

Product Hunt is the main live freshness source. It provides startup and product launch records with useful trend signals such as votes, comments, topics, launch date, tagline, description, and source URLs.

### Company Websites

When website enrichment is enabled, the app follows selected Product Hunt website URLs and extracts readable homepage or product-positioning text. This adds richer product context beyond the launch listing.

### Demo Sample Data

The app also includes a small offline sample dataset. This supports demonstrations and testing when external APIs are unavailable.

## RAG Pipeline Components

### 1. Ingestion

The app fetches recent launches from Product Hunt and optionally enriches selected products with company website text.

### 2. Normalization

Different source formats are converted into a common `StartupEvidence` structure. This lets the rest of the system treat Product Hunt records and website records consistently.

### 3. Chunking

Each evidence record is converted into source-aware chunks. The chunks include the startup name, source type, summary text, topics, sector, region, dates, and useful metadata.

### 4. Embedding

Chunks are embedded with Gemini embeddings. Each text chunk becomes a dense vector that represents semantic meaning.

### 5. Vector Storage

Vectors and metadata are stored in Pinecone. Pinecone becomes the retrieval layer that can find semantically relevant startup evidence for each user question.

### 6. Retrieval

When a user asks a question, the query is embedded and sent to Pinecone. Pinecone returns the closest matching evidence chunks before reranking.

### 7. Reranking And Trend Scoring

Retrieved chunks are reranked using semantic relevance and trend signals. The trend score considers recency, Product Hunt votes, Product Hunt comments, source diversity, evidence count, and sector or region match.

### 8. LLM Answer Generation

The final reranked chunks are formatted into a cited prompt and sent to Gemini. The model answers using only the supplied evidence and includes caveats when coverage is limited.

## What The User Sees

The Streamlit dashboard includes:

- a chat interface for multiple questions
- suggested demo questions
- live Gemini answer generation
- ranked startup evidence
- trend charts
- source URLs
- RAG trace with chunks, embeddings, Pinecone query details, pre-rerank output, reranked output, and exact LLM input

## Why This Is A Strong Submission

This project demonstrates the complete RAG lifecycle:

- live data ingestion
- chunking
- embeddings
- Pinecone vector search
- metadata-aware retrieval
- reranking
- prompt construction
- live LLM synthesis
- transparent debugging and explanation views
- user-facing dashboard design

It also avoids unsupported claims about funding, revenue, valuation, or investment potential unless that information exists in the retrieved evidence.

## Important Limitations

The system is an exploratory intelligence tool, not an investment advisor. Product Hunt data is biased toward launched products and technical audiences. Company website text can be marketing-heavy. The trend score is an explainable heuristic, not a prediction of future success.

## Future Improvements

Future versions could add:

- startup news ingestion
- YC or accelerator profile ingestion
- funding and investor data from reliable public sources
- scheduled background indexing
- persistent chat sessions
- richer evaluation metrics for retrieval quality
- more advanced cross-encoder reranking

## Repository Location

The project lives in:

```text
global_startup_radar/
```

Key files:

- `app.py`: Streamlit dashboard
- `src/startup_radar/`: RAG, ingestion, scoring, vector store, and chat logic
- `docs/architecture.md`: detailed architecture diagram and pipeline explanation
- `docs/scoring.md`: scoring and reranking explanation
- `docs/project_overview.pdf`: high-level PDF overview
