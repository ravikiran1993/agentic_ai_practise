from __future__ import annotations

import os

from startup_radar.environment import load_environment
from startup_radar.models import RetrievedEvidence


SYSTEM_PROMPT = """You are Global Startup Radar, a careful startup trend analyst.
Use only the supplied evidence. Cite sources with bracket numbers like [1].
Do not provide investment advice or unsupported claims about revenue, valuation, or returns.
If evidence is thin, say so clearly."""


def build_cited_context(evidence_items: list[RetrievedEvidence], limit: int = 8) -> str:
    """Format retrieved evidence as numbered context for an LLM prompt."""
    lines = []
    for index, item in enumerate(evidence_items[:limit], start=1):
        lines.append(
            "\n".join(
                [
                    f"[{index}] {item.startup_name}",
                    f"Source type: {item.source_type}",
                    f"Trend score: {item.trend_score}",
                    f"URL: {item.source_url}",
                    f"Evidence: {item.text}",
                ]
            )
        )
    return "\n\n".join(lines)


def build_answer_prompt(query: str, evidence_items: list[RetrievedEvidence], limit: int = 8) -> str:
    context = build_cited_context(evidence_items, limit=limit)
    return f"""{SYSTEM_PROMPT}

Question: {query}

Evidence:
{context}

Answer with:
- a short direct answer
- the most relevant startups and why they appear to be emerging
- citations for every factual claim
- a brief caveat about coverage limitations
"""


def create_chat_model(provider: str = "gemini", model: str | None = None, temperature: float = 0.2):
    """Create the Gemini chat model used for live answer generation."""
    normalized = provider.lower().strip()
    if normalized == "gemini":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:
            raise RuntimeError("Install langchain-google-genai to generate Gemini answers.")
        return ChatGoogleGenerativeAI(model=model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash"), temperature=temperature)
    raise ValueError(f"Unsupported LLM provider: {provider}")


def generate_answer(
    query: str,
    evidence_items: list[RetrievedEvidence],
    provider: str = "gemini",
    model: str | None = None,
) -> str:
    """Generate an answer using Gemini through LangChain."""
    load_environment()
    llm = create_chat_model(provider=provider, model=model)
    response = llm.invoke(build_answer_prompt(query, evidence_items))
    return str(response.content)

