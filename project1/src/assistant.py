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

import json
import os

import pandas as pd

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = (
    "You are a concise, insightful data analyst embedded in an interactive "
    "world food-production dashboard built on UN FAOSTAT data (crop & livestock "
    "production, 1961-2024). Answer using the DATA CONTEXT provided (all figures "
    "in million tonnes, Mt) together with your general knowledge of agriculture, "
    "economics and geography.\n\n"
    "You also have TOOLS to query the full dataset on demand. When a question "
    "needs figures not already in the context — a specific commodity, another "
    "year, a multi-year trend, or a full ranking — CALL THE TOOLS instead of "
    "guessing. Base any precise numbers on the context or tool results only; "
    "never invent figures. Keep answers short, clear and presentation-friendly."
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


def _post(messages: list[dict], tools: list | None = None,
          max_tokens: int = 900, temperature: float = 0.3) -> dict:
    """POST to the Groq chat-completions endpoint; return the parsed JSON."""
    key = get_api_key()
    if not key:
        raise RuntimeError("No GROQ_API_KEY configured.")
    import requests

    payload = {"model": get_model(), "messages": messages,
               "temperature": temperature, "max_tokens": max_tokens,
               "stream": False}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    resp = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
        json=payload, timeout=60,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Groq API error {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def _chat(messages: list[dict], max_tokens: int = 700,
          temperature: float = 0.4) -> str:
    return _post(messages, None, max_tokens, temperature)[
        "choices"][0]["message"]["content"].strip()


# --- Tools the model can call to query the FULL dataset on demand ----------
TOOLS = [
    {"type": "function", "function": {
        "name": "country_products",
        "description": "Top products a country produces in a given year, "
                       "ranked by tonnage.",
        "parameters": {"type": "object", "properties": {
            "country": {"type": "string"},
            "year": {"type": "integer"},
            "top_n": {"type": "integer", "description": "default 10"}},
            "required": ["country", "year"]}}},
    {"type": "function", "function": {
        "name": "commodity_top_producers",
        "description": "Which countries produced the most of a commodity "
                       "(an item like 'rice'/'wheat' or a category like "
                       "'beef') in a given year.",
        "parameters": {"type": "object", "properties": {
            "commodity": {"type": "string"},
            "year": {"type": "integer"},
            "top_n": {"type": "integer", "description": "default 10"}},
            "required": ["commodity", "year"]}}},
    {"type": "function", "function": {
        "name": "production_trend",
        "description": "A country's production of a commodity over a range of "
                       "years (yearly tonnage). Omit commodity for the "
                       "country's total output.",
        "parameters": {"type": "object", "properties": {
            "country": {"type": "string"},
            "commodity": {"type": "string"},
            "start_year": {"type": "integer", "description": "default 1961"},
            "end_year": {"type": "integer", "description": "default 2024"}},
            "required": ["country"]}}},
    {"type": "function", "function": {
        "name": "country_ranking",
        "description": "Countries ranked by total production tonnage in a "
                       "year. Optional group: 'Crops' or 'Livestock & meat'.",
        "parameters": {"type": "object", "properties": {
            "year": {"type": "integer"},
            "group": {"type": "string"},
            "top_n": {"type": "integer", "description": "default 15"}},
            "required": ["year"]}}},
]


def _resolve_country(df: pd.DataFrame, name: str):
    names = list(df["country"].unique())
    if name in names:
        return name
    low = name.strip().lower()
    if low in _ALIASES and _ALIASES[low] in names:
        return _ALIASES[low]
    for n in names:
        if n.lower() == low:
            return n
    cands = [n for n in names
             if low in n.lower() or n.lower().split(",")[0].strip() == low]
    return cands[0] if cands else None


def _commodity_mask(frame: pd.DataFrame, query: str):
    q = query.strip().lower()
    return (frame["item"].str.lower().str.contains(q, regex=False)
            | frame["category"].str.lower().str.contains(q, regex=False))


def _run_tool(df: pd.DataFrame, name: str, args: dict) -> dict:
    try:
        if name == "country_products":
            c = _resolve_country(df, args["country"])
            if not c:
                return {"error": f"country '{args['country']}' not found"}
            yr, n = int(args["year"]), int(args.get("top_n", 10))
            d = df[(df["country"] == c) & (df["year"] == yr)].nlargest(
                n, "value_tonnes")
            return {"country": c, "year": yr, "products": [
                {"item": r["item"], "category": r["category"],
                 "mt": round(r["value_tonnes"] / 1e6, 2)}
                for _, r in d.iterrows()]}

        if name == "commodity_top_producers":
            yr, n, q = int(args["year"]), int(args.get("top_n", 10)), args["commodity"]
            sub = df[(df["year"] == yr) & _commodity_mask(df, q)]
            if sub.empty:
                return {"error": f"no data for '{q}' in {yr}"}
            agg = sub.groupby("country")["value_tonnes"].sum().nlargest(n)
            return {"commodity": q, "year": yr, "matched_items":
                    sorted(sub["item"].unique())[:8], "top_producers": [
                        {"country": k, "mt": round(v / 1e6, 2)}
                        for k, v in agg.items()]}

        if name == "production_trend":
            c = _resolve_country(df, args["country"])
            if not c:
                return {"error": f"country '{args['country']}' not found"}
            s = int(args.get("start_year", 1961))
            e = int(args.get("end_year", 2024))
            d = df[(df["country"] == c) & (df["year"].between(s, e))]
            q = args.get("commodity")
            if q:
                d = d[_commodity_mask(d, q)]
            ser = d.groupby("year")["value_tonnes"].sum()
            return {"country": c, "commodity": q or "all output",
                    "trend": [{"year": int(y), "mt": round(v / 1e6, 2)}
                              for y, v in ser.items()]}

        if name == "country_ranking":
            yr, n = int(args["year"]), int(args.get("top_n", 15))
            grp = args.get("group")
            d = df[df["year"] == yr]
            if grp in ("Crops", "Livestock & meat"):
                d = d[d["group"] == grp]
            agg = d.groupby("country")["value_tonnes"].sum().nlargest(n)
            return {"year": yr, "group": grp or "all", "ranking": [
                {"rank": i + 1, "country": k, "mt": round(v / 1e6, 2)}
                for i, (k, v) in enumerate(agg.items())]}

        return {"error": f"unknown tool {name}"}
    except Exception as e:  # noqa: BLE001
        return {"error": f"tool '{name}' failed: {e}"}


def answer_question(question: str, context: str,
                    history: list[dict] | None = None,
                    df: pd.DataFrame | None = None) -> str:
    """Answer a question, letting the model call data tools when it needs more
    than the provided context (any country / commodity / year / trend)."""
    messages = [{"role": "system",
                 "content": SYSTEM_PROMPT + "\n\nDATA CONTEXT:\n" + context}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": question})

    use_tools = TOOLS if df is not None else None
    last = {}
    for _ in range(5):  # allow a few tool round-trips
        data = _post(messages, tools=use_tools)
        last = data["choices"][0]["message"]
        calls = last.get("tool_calls")
        if not calls:
            return (last.get("content") or "").strip() or "(no answer)"
        messages.append(last)  # echo assistant turn (with tool_calls)
        for tc in calls:
            fn = tc["function"]["name"]
            try:
                a = json.loads(tc["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                a = {}
            result = _run_tool(df, fn, a)
            messages.append({"role": "tool", "tool_call_id": tc["id"],
                             "name": fn, "content": json.dumps(result)})
    return (last.get("content") or "").strip() or \
        "I gathered the data but couldn't compose a final answer — try rephrasing."


def generate_insights(context: str, country: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"Based on the data context, give 3 short, interesting insights "
            f"about {country}'s food production. One bullet each, plain language, "
            f"presentation-friendly.\n\nDATA CONTEXT:\n{context}")},
    ]
    return _chat(messages, max_tokens=500)
