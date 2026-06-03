"""
Grok (xAI) data assistant for the food-production dashboard.

Builds a compact, factual context from the FAOSTAT dataframe (the selected
country's top products + trend, and that year's global leaders) and sends it to
the xAI Grok API so the model answers questions grounded in real figures.

The xAI API is OpenAI-compatible (https://api.x.ai/v1). Provide credentials via:
  * a local .env file:           XAI_API_KEY=xai-...
  * Streamlit Cloud secrets:     XAI_API_KEY = "xai-..."
Optionally set XAI_MODEL (defaults to "grok-2-latest").
"""
from __future__ import annotations

import os

import pandas as pd

XAI_URL = "https://api.x.ai/v1/chat/completions"
DEFAULT_MODEL = "grok-2-latest"

SYSTEM_PROMPT = (
    "You are a concise, insightful data analyst embedded in an interactive "
    "world food-production dashboard built on UN FAOSTAT data (crop & livestock "
    "production, 1961-2024). Answer using the DATA CONTEXT provided (all figures "
    "in million tonnes, Mt) together with your general knowledge of agriculture, "
    "economics and geography. Prefer the numbers in the context; if a specific "
    "figure isn't there, say so briefly and answer qualitatively. Keep answers "
    "short, clear and presentation-friendly. Never invent precise figures."
)


def _secret(name: str):
    """Read a value from Streamlit secrets, falling back to env vars."""
    try:
        import streamlit as st

        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name)


def get_api_key():
    return _secret("XAI_API_KEY")


def get_model() -> str:
    return _secret("XAI_MODEL") or DEFAULT_MODEL


def _mt(v: float) -> str:
    return f"{v / 1e6:,.1f}"


def build_context(df: pd.DataFrame, country: str, year: int,
                  top_n: int = 8) -> str:
    """A compact, factual snapshot the model can reason over."""
    lines = [
        "DATASET: UN FAO FAOSTAT 'Production: Crops and livestock products', "
        "production quantity in tonnes, 1961-2024, ~200 countries. All figures "
        "below are in MILLION TONNES (Mt).",
    ]

    c = df[df["country"] == country]
    cy = c[c["year"] == year].nlargest(top_n, "value_tonnes")
    lines.append(f"\nSELECTED COUNTRY: {country} — top {len(cy)} products in {year}:")
    for _, r in cy.iterrows():
        lines.append(f"  - {r['item']} ({r['category']}): {_mt(r['value_tonnes'])} Mt")

    catmix = (c[c["year"] == year].groupby("category")["value_tonnes"].sum()
              .sort_values(ascending=False))
    if not catmix.empty:
        lines.append(f"{country} output by category in {year}: "
                     + "; ".join(f"{k} {_mt(v)}" for k, v in catmix.items()))

    # Long-run trend: #1 product at start vs end of the record.
    def top_item(yr):
        d = c[c["year"] == yr].nlargest(1, "value_tonnes")
        return None if d.empty else (d.iloc[0]["item"], d.iloc[0]["value_tonnes"])

    y0, y1 = int(df["year"].min()), int(df["year"].max())
    a, b = top_item(y0), top_item(y1)
    if a and b:
        lines.append(f"{country} #1 product: {y0} = {a[0]} ({_mt(a[1])} Mt); "
                     f"{y1} = {b[0]} ({_mt(b[1])} Mt).")

    # Global snapshot for the selected year.
    g = df[df["year"] == year]
    top_countries = (g.groupby("country")["value_tonnes"].sum()
                     .sort_values(ascending=False).head(8))
    lines.append(f"\nGLOBAL SNAPSHOT {year} — largest producers by total tonnage: "
                 + "; ".join(f"{k} {_mt(v)}" for k, v in top_countries.items()))

    majors = ["Rice", "Wheat", "Maize (corn)", "Soya beans", "Sugar cane",
              "Potatoes", "Meat of chickens, fresh or chilled",
              "Meat of cattle with the bone, fresh or chilled",
              "Raw milk of cattle"]
    leaders = []
    for item in majors:
        gi = g[g["item"] == item]
        if not gi.empty:
            top = gi.nlargest(1, "value_tonnes").iloc[0]
            leaders.append(f"{item.split(',')[0].replace('Meat of ', '')} -> "
                           f"{top['country']} ({_mt(top['value_tonnes'])} Mt)")
    if leaders:
        lines.append(f"World's top producer by commodity in {year}: "
                     + "; ".join(leaders))

    return "\n".join(lines)


def _chat(messages: list[dict], max_tokens: int = 700,
          temperature: float = 0.4) -> str:
    key = get_api_key()
    if not key:
        raise RuntimeError("No XAI_API_KEY configured.")
    import requests

    resp = requests.post(
        XAI_URL,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
        json={"model": get_model(), "messages": messages,
              "temperature": temperature, "max_tokens": max_tokens,
              "stream": False},
        timeout=60,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"xAI API error {resp.status_code}: {resp.text[:300]}")
    return resp.json()["choices"][0]["message"]["content"].strip()


def answer_question(question: str, context: str,
                    history: list[dict] | None = None) -> str:
    messages = [{"role": "system",
                 "content": SYSTEM_PROMPT + "\n\nDATA CONTEXT:\n" + context}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": question})
    return _chat(messages)


def generate_insights(context: str, country: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"Based on the data context, give 3 short, interesting insights "
            f"about {country}'s food production. One bullet each, plain language, "
            f"presentation-friendly.\n\nDATA CONTEXT:\n{context}")},
    ]
    return _chat(messages, max_tokens=500)
