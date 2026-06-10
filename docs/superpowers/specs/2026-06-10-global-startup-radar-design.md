# Global Startup Radar Design

## Overview

Global Startup Radar is a Streamlit dashboard and RAG assistant for discovering emerging startups around the world. It uses LangChain for ingestion and orchestration, Pinecone for vector search, Product Hunt as a live trend signal, and an OpenAI API model for cited answer generation.

The project is designed as an MVP that is useful for exploration and strong enough for academic submission. It demonstrates a full RAG pipeline: source ingestion, text cleaning, chunking, metadata enrichment, embedding, vector indexing, semantic retrieval, reranking, trend scoring, and cited synthesis.

## Goals

- Help users ask questions about emerging global startups and receive grounded answers with citations.
- Rank startups using transparent trend signals, not only semantic similarity.
- Provide a dashboard experience with filters, charts, evidence snippets, and a ranked startup table.
- Keep cost low by using free/public data sources, Pinecone's free tier, cached ingestion, and small LLM calls.
- Include sample data so the app can run in demo mode if live API keys are unavailable.

## Non-Goals

- The system will not provide investment advice.
- The system will not claim that its trend score is a true funding, revenue, or valuation predictor.
- The MVP will not attempt exhaustive global startup coverage.
- The MVP will not depend on paid startup databases such as Crunchbase or Dealroom.

## Primary Data Sources

### Product Hunt API

Product Hunt is the primary freshness and launch-traction source. The app will ingest recent launches and capture product name, tagline, description, topics, launch date, votes, comments, makers when available, website URL, and Product Hunt URL.

### YC Company Directory

YC company data provides startup profiles, sectors, regions, descriptions, and batch information. It helps balance Product Hunt's product-launch bias with accelerator-backed startup metadata.

### Curated Startup News and RSS

Curated startup news sources provide funding announcements, market context, regional signals, and trend narratives. The MVP will support a small curated list of URLs or RSS feeds rather than broad web crawling.

### Company Websites

Company homepages, about pages, and product pages provide direct evidence about what each startup does. For the MVP, website ingestion will be limited to top or selected startups to avoid scraping complexity.

## Data Model

Each ingested item will be normalized into a common startup evidence record:

- `startup_name`
- `source_type`
- `source_name`
- `source_url`
- `title`
- `text`
- `published_at`
- `topics`
- `sector`
- `region`
- `country`
- `product_url`
- `product_hunt_votes`
- `product_hunt_comments`
- `yc_batch`
- `metadata`

Fields can be empty when a source does not provide them. The app will preserve source-specific metadata while exposing a common interface to retrieval and scoring.

## Chunking

The system will chunk by evidence type:

- Product Hunt launch chunks: product name, tagline, description, topics, launch date, votes, comments, and URL.
- Startup profile chunks: name, sector, location, batch, and company description.
- News chunks: title, summary or key paragraphs, publication date, source, and linked startup names when available.
- Website chunks: homepage/about/product text with page URL and startup name.

Chunks will be intentionally small and source-aware. Each chunk will include enough surrounding metadata to be useful when retrieved independently.

## Embeddings and Pinecone

Chunks will be embedded and stored in Pinecone with metadata. The Pinecone index will support semantic search plus metadata filtering by source, date, sector, region, and startup name.

The implementation will use environment variables for keys:

- `PRODUCT_HUNT_TOKEN`
- `PINECONE_API_KEY`
- `OPENAI_API_KEY`
- `PINECONE_INDEX_NAME`

The app will never hardcode API keys.

## Retrieval and Reranking

The retrieval pipeline will:

1. Accept a user query and optional dashboard filters.
2. Search Pinecone for top candidate chunks.
3. Apply metadata filters when selected.
4. Rerank candidates using semantic relevance and trend signals.
5. Group evidence by startup.
6. Build a compact cited context for the LLM.

The MVP reranker will be heuristic and explainable. It will combine:

- Pinecone similarity score.
- Query/topic match.
- Product Hunt votes.
- Product Hunt comments.
- Launch recency.
- YC batch recency.
- Evidence count.
- Source diversity.

Model-based reranking can be added later as an Option C extension if needed.

## Trend Score

Trend score will be an explainable heuristic, not a financial recommendation. The score will be displayed with component explanations where possible.

Initial formula:

```text
trend_score =
  semantic_relevance_weight
  + launch_recency_weight
  + product_hunt_votes_weight
  + product_hunt_comments_weight
  + source_diversity_weight
  + evidence_count_weight
  + sector_or_region_match_weight
```

The implementation will normalize each available component to a 0-1 scale and combine them into a 0-100 score for display.

## LLM Answer Generation

The LLM will receive only the reranked evidence snippets and metadata needed to answer the query. The answer prompt will require:

- Direct answer first.
- Startup names and short explanations.
- Citations to retrieved sources.
- Caveats when evidence is thin or biased.
- No unsupported investment claims.

## Streamlit Dashboard

The dashboard will include:

- Query box for natural-language startup trend questions.
- Sidebar filters for source, sector/topic, region, date range, and minimum trend score.
- Ranked startup table with name, sector, source count, latest source date, and trend score.
- Cited answer panel.
- Evidence snippets panel showing source URLs, snippet text, similarity score, and rerank score.
- Simple charts for top sectors, source mix, launch recency, and trend score distribution.

## Demo Mode

The project will include a small sample dataset or cached sample responses. Demo mode lets the app run without live API calls, which protects the submission from failing during grading because of missing keys, API limits, or network issues.

## Cost Controls

- Cache raw API responses locally.
- Cache normalized records and embeddings where practical.
- Keep default ingestion window small, such as the last 30-90 days.
- Limit LLM calls to final answer generation.
- Retrieve and rerank locally before constructing the LLM prompt.
- Use Pinecone free tier for the MVP.

## Error Handling

- Missing API keys will trigger clear setup messages and fall back to demo data where possible.
- API failures will be logged and surfaced in the dashboard without crashing the app.
- Empty retrieval results will produce a helpful answer explaining that no matching evidence was found.
- Ingestion scripts will validate required fields and skip malformed records.

## Testing and Validation

The project will include focused tests for:

- Normalizing source records.
- Chunking source documents.
- Computing trend scores.
- Reranking retrieved chunks.
- Formatting citations.
- Handling missing keys and empty results.

Manual validation will include:

- Running ingestion against demo data.
- Building or refreshing the Pinecone index.
- Asking representative startup trend questions.
- Checking that cited snippets support the generated answer.

## Future Extension: VC Analyst Copilot

After the MVP, the project can be extended toward a VC analyst copilot with:

- Startup comparison pages.
- Differentiation analysis.
- Risks and unknowns.
- "Why now?" market reasoning.
- Competitor maps.
- Optional model-based reranking.

These features are intentionally outside the MVP to keep the first version focused and deliverable.
