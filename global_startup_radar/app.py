from __future__ import annotations

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pandas as pd
import plotly.express as px
import streamlit as st

from startup_radar.chat import append_chat_turn, create_chat_turn
from startup_radar.chunking import chunk_evidence_record
from startup_radar.environment import apply_runtime_secrets, load_environment
from startup_radar.ingestion.sample_data import load_sample_records
from startup_radar.live_data import enrich_with_company_sites, load_product_hunt_evidence
from startup_radar.live_pipeline import build_pinecone_filter, index_evidence, search_indexed_evidence
from startup_radar.models import RetrievedEvidence
from startup_radar.rag import build_answer_prompt, generate_answer
from startup_radar.reranking import rerank_evidence
from startup_radar.trace import build_rag_trace
from startup_radar.vector_store import create_pinecone_vector_store


PROJECT_ROOT = Path(__file__).resolve().parent
SAMPLE_DATA = PROJECT_ROOT / "data" / "sample_startups.json"

load_environment(PROJECT_ROOT / ".env")


st.set_page_config(page_title="Global Startup Radar", layout="wide")
try:
    apply_runtime_secrets(st.secrets)
except FileNotFoundError:
    pass


@st.cache_data
def load_demo_evidence() -> list[RetrievedEvidence]:
    records = load_sample_records(SAMPLE_DATA)
    retrieved = []
    for record in records:
        chunk = chunk_evidence_record(record)[0]
        retrieved.append(
            RetrievedEvidence(
                chunk_id=chunk.id,
                startup_name=record.startup_name,
                text=chunk.text,
                source_url=record.source_url,
                source_type=record.source_type,
                similarity_score=0.72,
                metadata=chunk.metadata,
            )
        )
    return retrieved


@st.cache_data(ttl=900)
def load_live_product_hunt_evidence(
    first: int,
    posted_after: str | None,
    enrich_websites: bool,
    website_limit: int,
) -> list[RetrievedEvidence]:
    evidence = load_product_hunt_evidence(first=first, posted_after=posted_after or None)
    if enrich_websites:
        evidence = enrich_with_company_sites(evidence, limit=website_limit)
    return evidence


@st.cache_resource
def load_pinecone_store():
    return create_pinecone_vector_store()


def filter_evidence(
    evidence: list[RetrievedEvidence],
    sources: list[str],
    sectors: list[str],
    regions: list[str],
) -> list[RetrievedEvidence]:
    filtered = []
    for item in evidence:
        if sources and item.source_type not in sources:
            continue
        if sectors and item.metadata.get("sector") not in sectors:
            continue
        if regions and item.metadata.get("region") not in regions:
            continue
        filtered.append(item)
    return filtered


def to_dataframe(evidence: list[RetrievedEvidence]) -> pd.DataFrame:
    rows = []
    for item in evidence:
        rows.append(
            {
                "Startup": item.startup_name,
                "Sector": item.metadata.get("sector"),
                "Region": item.metadata.get("region"),
                "Source": item.source_type,
                "Published": item.metadata.get("published_at"),
                "Votes": item.metadata.get("product_hunt_votes", 0),
                "Comments": item.metadata.get("product_hunt_comments", 0),
                "Trend Score": item.trend_score,
                "Rerank Score": item.rerank_score,
                "URL": item.source_url,
            }
        )
    return pd.DataFrame(rows)


st.title("Global Startup Radar")
st.caption("LangChain + Pinecone-ready RAG dashboard for emerging startup discovery.")

with st.sidebar:
    st.header("Data")
    data_mode = st.radio("Data mode", ["Full live RAG", "Demo sample"], index=0)
    product_hunt_count = st.slider("Product Hunt launches", 5, 50, 25, 5)
    posted_after = st.text_input("Posted after date", value="")
    enrich_websites = st.toggle("Enrich with company websites", value=True)
    website_limit = st.slider("Company websites to read", 0, 15, 5, 1)

data_warning = None
live_pipeline_ready = False
vector_store = None
if data_mode == "Full live RAG":
    try:
        demo_items = load_live_product_hunt_evidence(
            product_hunt_count,
            posted_after,
            enrich_websites,
            website_limit,
        )
    except Exception as exc:
        data_warning = f"Live Product Hunt data is unavailable: {exc}. Falling back to demo data."
        demo_items = load_demo_evidence()
else:
    demo_items = load_demo_evidence()

all_sources = sorted({item.source_type for item in demo_items})
all_sectors = sorted({item.metadata.get("sector") for item in demo_items if item.metadata.get("sector")})
all_regions = sorted({item.metadata.get("region") for item in demo_items if item.metadata.get("region")})

with st.sidebar:
    st.header("Filters")
    selected_sources = st.multiselect("Sources", all_sources, default=all_sources)
    selected_sectors = st.multiselect("Sectors", all_sectors)
    selected_regions = st.multiselect("Regions", all_regions)
    min_trend_score = st.slider("Minimum trend score", 0, 100, 0)
    if st.button("Clear chat", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.latest_evidence = []
        st.session_state.latest_trace = {}

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "latest_evidence" not in st.session_state:
    st.session_state.latest_evidence = []
if "latest_trace" not in st.session_state:
    st.session_state.latest_trace = {}
if "indexed_signature" not in st.session_state:
    st.session_state.indexed_signature = ""

if data_mode == "Full live RAG" and not data_warning:
    try:
        vector_store = load_pinecone_store()
        index_signature = "|".join(sorted(item.chunk_id for item in demo_items))
        if st.session_state.indexed_signature != index_signature:
            with st.spinner("Embedding chunks with Gemini and indexing them in Pinecone..."):
                indexed_count = index_evidence(vector_store, demo_items)
            st.session_state.indexed_signature = index_signature
            st.success(f"Indexed {indexed_count} Product Hunt chunks into Pinecone.")
        live_pipeline_ready = True
    except Exception as exc:
        data_warning = f"Pinecone indexing/search is unavailable: {exc}. Using local reranking fallback."
        live_pipeline_ready = False

if data_warning:
    st.warning(data_warning)
if live_pipeline_ready:
    st.caption(f"Loaded {len(demo_items)} live Product Hunt records, embedded them with Gemini, and indexed them in Pinecone.")
else:
    st.caption(f"Loaded {len(demo_items)} evidence records from {data_mode}.")

default_query = "Which global AI startups are trending and why?"

filtered = filter_evidence(demo_items, selected_sources, selected_sectors, selected_regions)
dashboard_ranked = rerank_evidence(filtered, query=default_query, today="2026-06-10")
dashboard_ranked = [item for item in dashboard_ranked if item.trend_score >= min_trend_score]
df = to_dataframe(dashboard_ranked)

left, right = st.columns([1.3, 1])

with left:
    st.subheader("Startup trend chat")
    if not st.session_state.chat_history:
        st.info("Ask a question about startup sectors, regions, or traction signals to begin.")

    for turn in st.session_state.chat_history:
        with st.chat_message("user"):
            st.write(turn["question"])
        with st.chat_message("assistant"):
            st.write(turn["answer"])

    prompt = st.chat_input("Ask a follow-up about emerging startups")
    if prompt:
        source_chunks = filtered
        pinecone_filter = None
        pinecone_top_k = None
        if live_pipeline_ready and vector_store is not None:
            pinecone_filter = build_pinecone_filter(selected_sources, selected_sectors, selected_regions)
            pinecone_top_k = min(max(product_hunt_count, 10), 50)
            try:
                pinecone_results = search_indexed_evidence(
                    vector_store,
                    prompt,
                    k=pinecone_top_k,
                    metadata_filter=pinecone_filter,
                )
            except Exception as exc:
                st.warning(f"Pinecone retrieval failed, using local fallback: {exc}")
                pinecone_results = filtered
        else:
            pinecone_results = filtered

        turn_ranked = rerank_evidence(pinecone_results, query=prompt, today="2026-06-10")
        turn_ranked = [item for item in turn_ranked if item.trend_score >= min_trend_score]
        final_prompt = build_answer_prompt(prompt, turn_ranked[:8]) if turn_ranked else ""
        if not turn_ranked:
            answer = "No matching evidence was found for this question and filter set."
            answer_mode = "Live Gemini call"
        else:
            answer_mode = "Live Gemini call"
            try:
                answer = generate_answer(prompt, turn_ranked[:8], provider="gemini", model=os.getenv("GEMINI_MODEL"))
            except Exception as exc:
                answer = f"Live Gemini answer generation is unavailable: {exc}\n\nPrompt preview:\n\n{final_prompt}"

        trace = build_rag_trace(
            query=prompt,
            source_chunks=source_chunks,
            pinecone_results=pinecone_results,
            reranked=turn_ranked[:8],
            final_prompt=final_prompt,
            pinecone_filter=pinecone_filter,
            pinecone_top_k=pinecone_top_k,
        )
        st.session_state.latest_evidence = turn_ranked[:8]
        st.session_state.latest_trace = trace
        st.session_state.chat_history = append_chat_turn(
            st.session_state.chat_history,
            create_chat_turn(prompt, answer, turn_ranked[:8], answer_mode, trace),
        )
        st.rerun()

    st.subheader("Ranked startups")
    if df.empty:
        st.info("No evidence matches the selected filters.")
    else:
        st.dataframe(
            df[["Startup", "Sector", "Region", "Source", "Published", "Trend Score", "Rerank Score", "URL"]],
            use_container_width=True,
            hide_index=True,
        )

with right:
    st.subheader("Trend charts")
    if not df.empty:
        st.plotly_chart(px.bar(df, x="Startup", y="Trend Score", color="Sector"), use_container_width=True)
        st.plotly_chart(px.histogram(df, x="Source", color="Region"), use_container_width=True)

    st.subheader("Latest evidence")
    latest_evidence = st.session_state.latest_evidence or dashboard_ranked[:8]
    for index, item in enumerate(latest_evidence, start=1):
        with st.expander(f"[{index}] {item.startup_name} - score {item.trend_score}"):
            st.write(item.text)
            st.write(f"Source: {item.source_url}")
            st.json(
                {
                    "source_type": item.source_type,
                    "similarity_score": item.similarity_score,
                    "rerank_score": item.rerank_score,
                    "trend_score": item.trend_score,
                    "topics": item.metadata.get("topics"),
                }
            )

    st.subheader("Behind the scenes")
    latest_trace = st.session_state.latest_trace
    if not latest_trace:
        st.info("Ask a question to see chunks, embeddings, ranking, reranking, and the final LLM input.")
    else:
        st.caption(f"Trace for: {latest_trace['query']}")
        with st.expander("1. Source chunks prepared for indexing", expanded=False):
            st.dataframe(
                pd.DataFrame(latest_trace["source_chunks"])[
                    ["position", "startup_name", "source_type", "similarity_score", "text"]
                ],
                use_container_width=True,
                hide_index=True,
            )
        with st.expander("2. Gemini embedding and Pinecone query", expanded=False):
            st.write("Each source chunk is embedded with Gemini and stored as a vector in Pinecone.")
            st.json(latest_trace["pinecone_query"])
            st.write("Pinecone upsert input summary:")
            st.json(
                [
                    {
                        "chunk_id": item["chunk_id"],
                        "startup_name": item["startup_name"],
                        "source_type": item["source_type"],
                        "embedding_note": item["embedding_note"],
                    }
                    for item in latest_trace["source_chunks"]
                ]
            )
        with st.expander("3. Pinecone retrieval output before reranking", expanded=True):
            st.dataframe(
                pd.DataFrame(latest_trace["pinecone_results_before_rerank"])[
                    ["position", "startup_name", "source_type", "similarity_score", "text"]
                ],
                use_container_width=True,
                hide_index=True,
            )
        with st.expander("4. Final order after reranking", expanded=True):
            st.dataframe(
                pd.DataFrame(latest_trace["reranked_chunks"])[
                    ["position", "startup_name", "similarity_score", "trend_score", "rerank_score", "source_type"]
                ],
                use_container_width=True,
                hide_index=True,
            )
        with st.expander("5. Exact LLM input", expanded=False):
            st.code(latest_trace["llm_prompt"], language="markdown")
