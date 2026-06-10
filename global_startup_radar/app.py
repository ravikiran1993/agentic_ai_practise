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
from startup_radar.environment import load_environment
from startup_radar.ingestion.sample_data import load_sample_records
from startup_radar.models import RetrievedEvidence
from startup_radar.rag import build_answer_prompt, generate_answer
from startup_radar.reranking import rerank_evidence


PROJECT_ROOT = Path(__file__).resolve().parent
SAMPLE_DATA = PROJECT_ROOT / "data" / "sample_startups.json"

load_environment(PROJECT_ROOT / ".env")


st.set_page_config(page_title="Global Startup Radar", layout="wide")


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
    answer_mode = st.radio("Answer mode", ["Prompt preview", "Live Gemini call"], index=0)
    if st.button("Clear chat", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.latest_evidence = []

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "latest_evidence" not in st.session_state:
    st.session_state.latest_evidence = []

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
        turn_ranked = rerank_evidence(filtered, query=prompt, today="2026-06-10")
        turn_ranked = [item for item in turn_ranked if item.trend_score >= min_trend_score]
        if not turn_ranked:
            answer = "No matching evidence was found for this question and filter set."
        elif answer_mode == "Live Gemini call":
            try:
                answer = generate_answer(prompt, turn_ranked[:8], provider="gemini", model=os.getenv("GEMINI_MODEL"))
            except Exception as exc:
                answer = f"Live Gemini answer generation is unavailable: {exc}\n\nPrompt preview:\n\n{build_answer_prompt(prompt, turn_ranked[:8])}"
        else:
            answer = build_answer_prompt(prompt, turn_ranked[:8])

        st.session_state.latest_evidence = turn_ranked[:8]
        st.session_state.chat_history = append_chat_turn(
            st.session_state.chat_history,
            create_chat_turn(prompt, answer, turn_ranked[:8], answer_mode),
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
