from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pandas as pd
import plotly.express as px
import streamlit as st

from startup_radar.chunking import chunk_evidence_record
from startup_radar.ingestion.sample_data import load_sample_records
from startup_radar.models import RetrievedEvidence
from startup_radar.rag import build_answer_prompt, generate_answer
from startup_radar.reranking import rerank_evidence


PROJECT_ROOT = Path(__file__).resolve().parent
SAMPLE_DATA = PROJECT_ROOT / "data" / "sample_startups.json"


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
    answer_mode = st.radio("Answer mode", ["Prompt preview", "Live OpenAI call"], index=0)

query = st.text_input(
    "Ask a startup trend question",
    value="Which global AI startups are trending and why?",
)

filtered = filter_evidence(demo_items, selected_sources, selected_sectors, selected_regions)
ranked = rerank_evidence(filtered, query=query, today="2026-06-10")
ranked = [item for item in ranked if item.trend_score >= min_trend_score]
df = to_dataframe(ranked)

left, right = st.columns([1.3, 1])

with left:
    st.subheader("Ranked startups")
    if df.empty:
        st.info("No evidence matches the selected filters.")
    else:
        st.dataframe(
            df[["Startup", "Sector", "Region", "Source", "Published", "Trend Score", "Rerank Score", "URL"]],
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("RAG answer")
    if not ranked:
        st.write("No matching evidence was found for this query and filter set.")
    elif answer_mode == "Live OpenAI call":
        try:
            st.write(generate_answer(query, ranked[:8]))
        except Exception as exc:
            st.warning(f"Live answer generation is unavailable: {exc}")
            st.code(build_answer_prompt(query, ranked[:8]), language="markdown")
    else:
        st.code(build_answer_prompt(query, ranked[:8]), language="markdown")

with right:
    st.subheader("Trend charts")
    if not df.empty:
        st.plotly_chart(px.bar(df, x="Startup", y="Trend Score", color="Sector"), use_container_width=True)
        st.plotly_chart(px.histogram(df, x="Source", color="Region"), use_container_width=True)

    st.subheader("Evidence snippets")
    for index, item in enumerate(ranked[:8], start=1):
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
