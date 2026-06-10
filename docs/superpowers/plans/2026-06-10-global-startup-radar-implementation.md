# Global Startup Radar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-contained Streamlit + LangChain + Pinecone RAG project for discovering and explaining emerging global startups.

**Architecture:** The project lives in `global_startup_radar/`. Pure Python modules handle evidence records, chunking, scoring, reranking, Product Hunt ingestion, vector indexing, and RAG answer generation; `app.py` provides the Streamlit dashboard. Tests cover the pure logic so the system can be verified without live API keys.

**Tech Stack:** Python, Streamlit, LangChain, Pinecone, OpenAI API, Product Hunt GraphQL API, unittest.

---

### Task 1: Core Data Model and Pipeline Logic

**Files:**
- Create: `global_startup_radar/src/startup_radar/models.py`
- Create: `global_startup_radar/src/startup_radar/chunking.py`
- Create: `global_startup_radar/src/startup_radar/scoring.py`
- Create: `global_startup_radar/src/startup_radar/reranking.py`
- Test: `global_startup_radar/tests/test_pipeline_core.py`

- [ ] Write failing tests for chunk creation, trend score normalization, and reranking order.
- [ ] Run `python -m unittest discover global_startup_radar/tests` and confirm imports fail because modules do not exist.
- [ ] Implement dataclasses and pure functions.
- [ ] Run `python -m unittest discover global_startup_radar/tests` and confirm tests pass.

### Task 2: Ingestion, Sample Data, and RAG Integration

**Files:**
- Create: `global_startup_radar/src/startup_radar/ingestion/product_hunt.py`
- Create: `global_startup_radar/src/startup_radar/ingestion/sample_data.py`
- Create: `global_startup_radar/src/startup_radar/vector_store.py`
- Create: `global_startup_radar/src/startup_radar/rag.py`
- Create: `global_startup_radar/data/sample_startups.json`
- Test: `global_startup_radar/tests/test_ingestion_and_rag.py`

- [ ] Write failing tests for sample loading, Product Hunt response normalization, citation formatting, and prompt context creation.
- [ ] Run `python -m unittest discover global_startup_radar/tests` and confirm new tests fail because modules do not exist.
- [ ] Implement ingestion helpers, vector store wrapper, and RAG prompt assembly.
- [ ] Run `python -m unittest discover global_startup_radar/tests` and confirm tests pass.

### Task 3: Streamlit App and Documentation

**Files:**
- Create: `global_startup_radar/app.py`
- Create: `global_startup_radar/README.md`
- Create: `global_startup_radar/requirements.txt`
- Create: `global_startup_radar/.env.example`
- Create: `global_startup_radar/src/startup_radar/__init__.py`
- Create: `global_startup_radar/src/startup_radar/ingestion/__init__.py`

- [ ] Create Streamlit dashboard with query input, filters, ranked table, charts, answer panel, and evidence panel.
- [ ] Write setup and architecture documentation for humans.
- [ ] Run `python -m unittest discover global_startup_radar/tests`.
- [ ] Run `python -m py_compile` over project Python files.

### Task 4: GitHub Publication

**Files:**
- Modify Git metadata only.

- [ ] Set repo-local Git author identity if missing.
- [ ] Configure remote `origin` as `https://github.com/ravikiran-uppalapati/agentic_ai_practise.git` if needed.
- [ ] Stage project files and specs.
- [ ] Commit with message `Add Global Startup Radar RAG project`.
- [ ] Push to the GitHub repository.
