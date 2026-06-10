# Global Startup Radar

Global Startup Radar is a Streamlit dashboard and RAG pipeline for discovering emerging startups around the world. It combines startup evidence from Product Hunt, YC-style startup profiles, curated news, and company websites, then uses chunking, embeddings, Pinecone retrieval, reranking, and LLM synthesis to answer startup trend questions with citations.

The project is built for a clear academic/demo submission: it shows every important RAG step instead of hiding the pipeline behind a chatbot.

## What The Project Does

Users can ask questions such as:

- Which global AI startups are trending and why?
- What climate tech startups are emerging in Europe?
- Which developer tool startups show strong launch traction?
- What evidence supports each startup recommendation?

The dashboard returns:

- a ranked startup table
- trend scores
- evidence snippets
- source URLs
- charts by sector/source/region
- a prompt preview or live OpenAI-generated answer

## Why This Is More Than A Basic RAG Chatbot

This project includes the full retrieval pipeline:

1. **Ingestion** from Product Hunt and local/sample startup evidence.
2. **Normalization** into a common `StartupEvidence` model.
3. **Chunking** into source-aware evidence chunks.
4. **Embedding** through LangChain/OpenAI.
5. **Vector storage** in Pinecone.
6. **Semantic retrieval** from Pinecone.
7. **Reranking** using semantic relevance and trend signals.
8. **Trend scoring** using votes, comments, recency, source diversity, and evidence count.
9. **Answer generation** with cited evidence and caveats.
10. **Dashboard exploration** through Streamlit.

## Folder Structure

```text
global_startup_radar/
  app.py                         Streamlit dashboard
  README.md                      Human-readable project guide
  requirements.txt               Python dependencies
  .env.example                   Required environment variables
  data/
    sample_startups.json         Demo dataset for offline use
  src/startup_radar/
    models.py                    Core dataclasses
    chunking.py                  Evidence chunk generation
    scoring.py                   Trend score calculation
    reranking.py                 Evidence reranking
    rag.py                       Prompt and answer generation helpers
    vector_store.py              LangChain/Pinecone wrapper
    ingestion/
      product_hunt.py            Product Hunt GraphQL ingestion
      sample_data.py             Local sample data loader
  tests/
    test_pipeline_core.py        Chunking, scoring, reranking tests
    test_ingestion_and_rag.py    Ingestion and prompt tests
```

## Data Sources

### Product Hunt API

Product Hunt is the main freshness source. It provides launch details such as product name, tagline, description, topics, votes, comments, launch date, and URL. This helps the system identify startups and products getting recent attention.

### YC-Style Startup Profiles

YC-style profile data adds startup metadata such as sector, geography, batch, and company description. In the MVP, this can be represented through curated/sample records and later expanded with a dedicated loader.

### Curated News and Company Websites

News articles and company pages provide context about funding, positioning, product claims, and market narratives. The MVP supports the normalized evidence model needed for these sources.

## RAG Pipeline

```text
Raw source data
  -> StartupEvidence records
  -> EvidenceChunk records
  -> Embeddings
  -> Pinecone index
  -> Semantic retrieval
  -> Reranking
  -> Cited LLM prompt
  -> Streamlit dashboard answer
```

## Trend Score

The trend score is an explainable heuristic from 0 to 100. It is not investment advice and should not be treated as a revenue, valuation, or funding predictor.

The MVP combines:

- semantic relevance
- launch recency
- Product Hunt votes
- Product Hunt comments
- source diversity
- evidence count
- sector or region match

## Setup

Create and activate a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file from the template:

```bash
copy .env.example .env
```

Fill in:

```text
PRODUCT_HUNT_TOKEN=...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=global-startup-radar
OPENAI_API_KEY=...
```

## Run The Dashboard

```bash
streamlit run app.py
```

By default, the app runs in demo mode using `data/sample_startups.json`. This means the project can be opened and understood even before API keys are configured.

## Running Tests

From the repository root:

```bash
python -m unittest discover global_startup_radar/tests
```

The tests intentionally focus on pure logic that does not require paid services:

- chunk creation
- Product Hunt response normalization
- sample data loading
- trend score calculation
- evidence reranking
- cited prompt context generation

## Live Integration Path

The live integration path is:

1. Use `startup_radar.ingestion.product_hunt.fetch_recent_product_hunt_posts()` to fetch recent launches.
2. Normalize posts with `product_hunt_post_to_evidence()`.
3. Chunk records with `chunk_evidence_record()`.
4. Create a Pinecone vector store with `create_pinecone_vector_store()`.
5. Upsert chunks with `upsert_chunks()`.
6. Retrieve evidence with `search_vector_store()`.
7. Rerank with `rerank_evidence()`.
8. Generate an answer with `generate_answer()`.

## Cost Controls

- The sample dataset works without external services.
- Product Hunt ingestion is separate from dashboard rendering.
- Embeddings and Pinecone writes should be run intentionally, not on every page refresh.
- The dashboard defaults to prompt preview mode.
- Live OpenAI calls only happen when the user selects "Live OpenAI call".

## Limitations

- Product Hunt is biased toward product launches and technical audiences.
- YC-style data is biased toward accelerator-backed startups.
- News data favors companies that receive media coverage.
- The trend score is a transparent heuristic, not a ground-truth ranking.
- The demo dataset is intentionally small.

## Future Extension

The next version can become a VC-style analyst copilot with:

- startup comparison pages
- "why now?" analysis
- competitor mapping
- risks and unknowns
- market attractiveness summaries
- model-based reranking

The current MVP keeps these out of scope so the project stays focused, testable, and easy to explain.
