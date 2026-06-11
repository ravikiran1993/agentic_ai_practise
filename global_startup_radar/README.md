# Global Startup Radar

Global Startup Radar is a Streamlit dashboard and live RAG pipeline for discovering emerging startups around the world. It combines startup evidence from Product Hunt and selected company websites with chunking, Gemini embeddings, Pinecone retrieval, reranking, and Gemini synthesis to answer startup trend questions with citations.

The project is built for a clear academic/demo submission: it shows every important RAG step instead of hiding the pipeline behind a chatbot.

For a detailed visual architecture diagram, see [docs/architecture.md](docs/architecture.md). For the scoring and reranking explanation, see [docs/scoring.md](docs/scoring.md).

## What The Project Does

Users can ask questions such as:

- Which global AI startups are trending and why?
- What climate tech startups are emerging in Europe?
- Which developer tool startups show strong launch traction?
- What evidence supports each startup recommendation?

The dashboard returns:

- a chat-style question and answer history
- suggested demo questions users can click
- a ranked startup table
- trend scores
- evidence snippets
- a behind-the-scenes RAG trace for each question
- source URLs
- charts by sector/source/region
- a live Gemini-generated answer

## Why This Is More Than A Basic RAG Chatbot

This project includes the full retrieval pipeline:

1. **Ingestion** from Product Hunt and local/sample startup evidence.
2. **Normalization** into a common `StartupEvidence` model.
3. **Chunking** into source-aware evidence chunks.
4. **Embedding** through LangChain/Gemini.
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

Company websites provide context about product positioning, target users, features, and claims. In full live mode, the app can follow Product Hunt website URLs for a limited number of companies, extract readable homepage text, create website evidence chunks, and index those chunks alongside Product Hunt launch chunks.

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

Detailed scoring documentation is available in [docs/scoring.md](docs/scoring.md).

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
GOOGLE_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash
GEMINI_EMBEDDING_MODEL=models/gemini-embedding-001
GEMINI_EMBEDDING_DIMENSION=1024
```

## Run The Dashboard

```bash
streamlit run app.py
```

By default, the app runs in **Full live RAG** mode. It fetches Product Hunt launches, optionally enriches them with company website text, embeds the chunks with Gemini, indexes them in Pinecone, retrieves from Pinecone for each question, reranks the retrieved evidence, and sends the final cited prompt to Gemini.

If you need an offline fallback, switch **Data mode** in the sidebar to **Demo sample**. Demo mode contains five sample startups and does not require external API calls.

Use the suggested question buttons for guided demos, or use the chat input at the bottom of the main panel to ask custom startup-trend questions. In full live mode, each question retrieves semantically relevant chunks from Pinecone before reranking and answer generation.

The **Behind the scenes** panel shows how each question moves through the RAG pipeline: source chunks prepared for indexing, Gemini embedding/Pinecone query details, Pinecone retrieval output before reranking, final order after reranking, scores, and the exact prompt sent to the LLM.

## Deploy To Streamlit Community Cloud

Use these settings when creating the app:

```text
Repository: ravikiran-uppalapati/agentic_ai_practise
Branch: main
Main file path: global_startup_radar/app.py
```

In **Advanced settings**, paste secrets in TOML format:

```toml
PRODUCT_HUNT_TOKEN = "your-product-hunt-token"
PINECONE_API_KEY = "your-pinecone-api-key"
PINECONE_INDEX_NAME = "global-startup-radar"
GOOGLE_API_KEY = "your-gemini-api-key"
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_EMBEDDING_MODEL = "models/gemini-embedding-001"
GEMINI_EMBEDDING_DIMENSION = "1024"
```

Do not commit `.env` or `.streamlit/secrets.toml`. The app reads local `.env` during development and Streamlit Cloud secrets during deployment.

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

## LLM Providers

The dashboard uses Gemini for live answer generation through `GOOGLE_API_KEY`, using `gemini-2.5-flash` by default. You can override the model with `GEMINI_MODEL` in `.env`.

The dashboard uses Gemini live for chat answers. The behind-the-scenes panel still shows the exact LLM prompt for inspection after each question.

## Live Integration Path

The live integration path is:

1. Use `startup_radar.ingestion.product_hunt.fetch_recent_product_hunt_posts()` to fetch recent launches.
2. Normalize posts with `product_hunt_post_to_evidence()`.
3. Optionally fetch selected company websites with `fetch_company_site_to_evidence()`.
4. Chunk records with `chunk_evidence_record()`.
5. Embed chunks with Gemini embeddings.
6. Upsert vectors into Pinecone with `index_evidence()`.
7. Retrieve relevant evidence from Pinecone with `search_indexed_evidence()`.
8. Rerank with `rerank_evidence()`.
9. Generate an answer with `generate_answer()`.

## Cost Controls

- The sample dataset works without external services.
- Product Hunt ingestion is separate from dashboard rendering.
- Embeddings and Pinecone writes should be run intentionally, not on every page refresh.
- Gemini calls happen when the user submits a chat question.
- The behind-the-scenes trace shows the exact prompt used for each Gemini call.

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
