"""
Groq-powered data assistant for the food-production dashboard.

Builds a compact, factual context from the FAOSTAT dataframe (the selected
country's top products + trend, and that year's global leaders) and sends it to
the Groq API so the model answers questions grounded in real figures.

Groq offers a free API tier (no credit card) running fast open models, and its
endpoint is OpenAI-compatible (https://api.groq.com/openai/v1). Provide creds via:
  * a local .env file:           GROQ_API_KEY=gsk_...
  * Streamlit Cloud secrets:     GROQ_API_KEY = "gsk_..."
Optionally set GROQ_MODEL (defaults to "llama-3.3-70b-versatile").

NOTE: "Groq" (this, free) is a different company from "Grok" (xAI, paid).
"""
from __future__ import annotations

import os

import pandas as pd

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"

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
    return _secret("GROQ_API_KEY")


def get_model() -> str:
    return _secret("GROQ_MODEL") or DEFAULT_MODEL


def _mt(v: float) -> str:
    return f"{v / 1e6:,.1f}"


_ALIASES = {
    "usa": "United States of America", "u.s.": "United States of America",
    "us": "United States of America", "america": "United States of America",
    "uk": "United Kingdom of Great Britain and Northern Ireland",
    "britain": "United Kingdom of Great Britain and Northern Ireland",
    "england": "United Kingdom of Great Britain and Northern Ireland",
    "russia": "Russian Federation", "china": "China, mainland",
    "south korea": "Republic of Korea", "north korea":
    "Democratic People's Republic of Korea", "iran":
    "Iran (Islamic Republic of)", "uae": "United Arab Emirates",
    "vietnam": "Viet Nam", "tanzania": "United Republic of Tanzania",
    "bolivia": "Bolivia (Plurinational State of)",
    "venezuela": "Venezuela (Bolivarian Republic of)", "syria":
    "Syrian Arab Republic", "laos": "Lao People's Democratic Republic",
}


def _mentioned_countries(df: pd.DataFrame, question: str,
                         exclude: str | None = None) -> list[str]:
    """Country names referenced in the user's question (best-effort match)."""
    ql = f" {question.lower()} "
    names = list(df["country"].unique())
    hits = []
    for n in names:
        key = n.lower()
        short = key.split(",")[0].split("(")[0].strip()
        if key in ql or (len(short) > 3 and f" {short} " in ql):
            hits.append(n)
    for alias, full in _ALIASES.items():
        if f" {alias} " in ql and full in names and full not in hits:
            hits.append(full)
    if exclude:
        hits = [h for h in hits if h != exclude]
    return list(dict.fromkeys(hits))


def build_context(df: pd.DataFrame, country: str, year: int,
                  top_n: int = 8, question: str | None = None) -> str:
    """A compact, factual snapshot the model can reason over.

    When ``question`` is given, the context also includes any countries named
    in the question (with their top products), so the assistant can answer
    about countries other than the selected one.
    """
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

    # Every country's #1 product this year, so the model can answer about ANY
    # country (e.g. Japan) and "which countries' top product is X" questions.
    top_by_country = (g.sort_values("value_tonnes", ascending=False)
                      .groupby("country", sort=True).first())
    lines.append(f"\nWORLD — each country's #1 product in {year} "
                 "(country: product, Mt):")
    for cname, r in top_by_country.sort_index().iterrows():
        lines.append(f"  - {cname}: {r['item'].split(',')[0]} "
                     f"({_mt(r['value_tonnes'])})")

    # Deeper detail for any countries explicitly named in the question.
    if question:
        for mc in _mentioned_countries(df, question, exclude=country)[:3]:
            md = df[(df["country"] == mc) & (df["year"] == year)].nlargest(
                top_n, "value_tonnes")
            if md.empty:
                continue
            lines.append(f"\n{mc} — top {len(md)} products in {year}:")
            for _, r in md.iterrows():
                lines.append(f"  - {r['item']} ({r['category']}): "
                             f"{_mt(r['value_tonnes'])} Mt")

    return "\n".join(lines)


def _chat(messages: list[dict], max_tokens: int = 700,
          temperature: float = 0.4) -> str:
    key = get_api_key()
    if not key:
        raise RuntimeError("No GROQ_API_KEY configured.")
    import requests

    resp = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
        json={"model": get_model(), "messages": messages,
              "temperature": temperature, "max_tokens": max_tokens,
              "stream": False},
        timeout=60,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Groq API error {resp.status_code}: {resp.text[:300]}")
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
