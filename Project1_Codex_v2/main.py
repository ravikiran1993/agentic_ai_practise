from __future__ import annotations

import os
import re
from html import escape
from io import BytesIO
from zipfile import ZipFile

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from dotenv import load_dotenv


FAOSTAT_QCL_URL = (
    "https://fenixservices.fao.org/faostat/static/bulkdownloads/"
    "Production_Crops_Livestock_E_All_Data_(Normalized).zip"
)
GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
OWID_CROP_SOURCES = {
    "Wheat": "https://ourworldindata.org/grapher/wheat-production.csv",
    "Maize": "https://ourworldindata.org/grapher/maize-production.csv",
    "Rice": "https://ourworldindata.org/grapher/rice-production.csv",
    "Barley": "https://ourworldindata.org/grapher/barley-production.csv",
    "Soybeans": "https://ourworldindata.org/grapher/soybean-production.csv",
    "Potatoes": "https://ourworldindata.org/grapher/potato-production.csv",
    "Cassava": "https://ourworldindata.org/grapher/cassava-production.csv",
}

CROP_GROUPS = {
    "Cereals": ["wheat", "rice", "maize", "barley", "oats", "rye", "sorghum", "millet"],
    "Fruit": ["apple", "banana", "orange", "grape", "mango", "pineapple", "strawberry"],
    "Vegetables": ["tomato", "onion", "potato", "carrot", "cabbage", "pepper"],
    "Oil crops": ["soybean", "rapeseed", "sunflower", "groundnut", "palm", "olive"],
    "Cash crops": ["coffee", "cocoa", "tea", "cotton", "sugar cane", "tobacco"],
}

DEMO_DATA = pd.DataFrame(
    [
        ("United Kingdom", "Wheat", 2019, 16225),
        ("United Kingdom", "Wheat", 2020, 9658),
        ("United Kingdom", "Wheat", 2021, 13988),
        ("United Kingdom", "Wheat", 2022, 15150),
        ("United Kingdom", "Wheat", 2023, 14022),
        ("United Kingdom", "Barley", 2019, 8156),
        ("United Kingdom", "Barley", 2020, 8117),
        ("United Kingdom", "Barley", 2021, 6988),
        ("United Kingdom", "Barley", 2022, 7385),
        ("United Kingdom", "Barley", 2023, 7076),
        ("India", "Rice", 2019, 177645),
        ("India", "Rice", 2020, 186000),
        ("India", "Rice", 2021, 195425),
        ("India", "Rice", 2022, 196245),
        ("India", "Rice", 2023, 204671),
        ("Brazil", "Soybeans", 2019, 114269),
        ("Brazil", "Soybeans", 2020, 121797),
        ("Brazil", "Soybeans", 2021, 134935),
        ("Brazil", "Soybeans", 2022, 120701),
        ("Brazil", "Soybeans", 2023, 152145),
        ("Ethiopia", "Coffee, green", 2019, 469),
        ("Ethiopia", "Coffee, green", 2020, 584),
        ("Ethiopia", "Coffee, green", 2021, 456),
        ("Ethiopia", "Coffee, green", 2022, 497),
        ("Ethiopia", "Coffee, green", 2023, 501),
    ],
    columns=["Area", "Item", "Year", "Value"],
)


st.set_page_config(page_title="FAOSTAT Crop Dashboard", layout="wide")
load_dotenv()


@st.cache_data(show_spinner=False)
def load_faostat_qcl() -> tuple[pd.DataFrame, bool, str]:
    """Load FAOSTAT crop production data, returning demo rows if offline."""
    try:
        response = requests.get(FAOSTAT_QCL_URL, timeout=45)
        response.raise_for_status()

        with ZipFile(BytesIO(response.content)) as archive:
            csv_name = next(name for name in archive.namelist() if name.endswith(".csv"))
            usecols = ["Area", "Element", "Item", "Year", "Unit", "Value"]
            data = pd.read_csv(archive.open(csv_name), usecols=usecols)

        data = normalize_faostat_data(data)
        data, is_live, source_note = ensure_usable_data(data, True, "Live FAOSTAT QCL bulk download")
        if is_live:
            return data, is_live, source_note
        return load_owid_crop_data()
    except Exception as exc:
        try:
            return load_owid_crop_data()
        except Exception as fallback_exc:
            return (
                DEMO_DATA.copy(),
                False,
                f"Demo data because FAOSTAT failed ({exc}) and OWID fallback failed ({fallback_exc})",
            )


def normalize_faostat_data(data: pd.DataFrame) -> pd.DataFrame:
    production = data[
        data["Element"].astype(str).str.casefold().eq("production")
        & data["Unit"].astype(str).str.casefold().isin(["t", "tonnes"])
        & data["Value"].notna()
    ][["Area", "Item", "Year", "Value"]].copy()
    production["Year"] = pd.to_numeric(production["Year"], errors="coerce").astype("Int64")
    production["Value"] = pd.to_numeric(production["Value"], errors="coerce")
    production = production.dropna(subset=["Area", "Item", "Year", "Value"])
    production["Year"] = production["Year"].astype(int)
    return production


def load_owid_crop_data() -> tuple[pd.DataFrame, bool, str]:
    frames = []
    for crop, url in OWID_CROP_SOURCES.items():
        raw = pd.read_csv(url)
        frames.append(normalize_owid_crop_data(raw, crop))

    data = pd.concat(frames, ignore_index=True)
    note = "OWID Grapher crop production CSVs, derived from FAOSTAT crop production data"
    return ensure_usable_data(data, False, note)


def normalize_owid_crop_data(data: pd.DataFrame, crop: str) -> pd.DataFrame:
    value_column = next(column for column in data.columns if column not in {"Entity", "Code", "Year"})
    normalized = data[["Entity", "Code", "Year", value_column]].copy()
    normalized = normalized[
        normalized["Code"].notna()
        & normalized["Code"].astype(str).str.len().eq(3)
        & ~normalized["Code"].astype(str).str.startswith("OWID")
        & ~normalized["Entity"].astype(str).str.contains(r"\(FAO\)", regex=True)
        & normalized[value_column].notna()
    ]
    normalized = normalized.rename(
        columns={
            "Entity": "Area",
            value_column: "Value",
        }
    )
    normalized["Item"] = crop
    normalized["Year"] = pd.to_numeric(normalized["Year"], errors="coerce").astype("Int64")
    normalized["Value"] = pd.to_numeric(normalized["Value"], errors="coerce")
    normalized = normalized.dropna(subset=["Area", "Item", "Year", "Value"])
    normalized["Year"] = normalized["Year"].astype(int)
    return normalized[["Area", "Item", "Year", "Value"]]


def ensure_usable_data(
    data: pd.DataFrame,
    is_live: bool,
    source_note: str,
) -> tuple[pd.DataFrame, bool, str]:
    required_columns = {"Area", "Item", "Year", "Value"}
    has_required_columns = required_columns.issubset(data.columns)
    has_countries = has_required_columns and len(data["Area"].dropna().unique()) > 0
    has_years = has_required_columns and data["Year"].notna().any()

    if has_countries and has_years and not data.empty:
        return data, is_live, source_note

    note = f"Demo data because FAOSTAT returned no usable crop production rows. Previous source: {source_note}"
    return DEMO_DATA.copy(), False, note


def format_tonnes(value: float) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M t"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K t"
    return f"{value:,.0f} t"


def group_options(items: list[str]) -> list[str]:
    options = ["All crops"]
    for group, keywords in CROP_GROUPS.items():
        if any(any(keyword in item.lower() for keyword in keywords) for item in items):
            options.append(group)
    return options


def apply_group_filter(data: pd.DataFrame, selected_group: str) -> pd.DataFrame:
    if selected_group == "All crops":
        return data

    keywords = CROP_GROUPS[selected_group]
    pattern = "|".join(keywords)
    return data[data["Item"].str.lower().str.contains(pattern, regex=True, na=False)]


def build_top_crop_map_data(
    data: pd.DataFrame,
    selected_items: list[str],
    comparison_year: int,
) -> pd.DataFrame:
    if not selected_items:
        return pd.DataFrame(columns=["Area", "Item", "Value", "ValueLabel"])

    comparison = data[
        data["Item"].isin(selected_items)
        & data["Year"].eq(comparison_year)
    ]
    if comparison.empty:
        return pd.DataFrame(columns=["Area", "Item", "Value", "ValueLabel"])

    totals = comparison.groupby(["Area", "Item"], as_index=False)["Value"].sum()
    top_indexes = totals.groupby("Area")["Value"].idxmax()
    map_data = totals.loc[top_indexes].sort_values(["Item", "Area"]).reset_index(drop=True)
    map_data["ValueLabel"] = map_data["Value"].map(format_tonnes)
    return map_data


def build_assistant_context(
    data: pd.DataFrame,
    country: str,
    selected_items: list[str],
    year_range: tuple[int, int],
    comparison_year: int,
    source_note: str,
    question: str = "",
) -> str:
    context_areas = build_context_areas(data, country, question)
    context_items = build_context_items(data, selected_items, question)
    scoped = data[
        data["Area"].isin(context_areas)
        & data["Item"].isin(context_items)
        & data["Year"].between(year_range[0], year_range[1])
    ]
    latest_year = int(scoped["Year"].max()) if not scoped.empty else comparison_year
    latest = (
        scoped[scoped["Year"].eq(latest_year)]
        .groupby(["Area", "Item"], as_index=False)["Value"]
        .sum()
        .sort_values(["Area", "Value"], ascending=[True, False])
        .head(20)
    )

    leaders = (
        data[data["Item"].isin(context_items) & data["Year"].eq(comparison_year)]
        .groupby("Area", as_index=False)["Value"]
        .sum()
        .sort_values("Value", ascending=False)
        .head(10)
    )

    top_crops = ", ".join(
        f"{row.Area} - {row.Item}: {format_tonnes(float(row.Value))}"
        for row in latest.itertuples(index=False)
    ) or "No selected crop rows"
    top_countries = ", ".join(
        f"{row.Area}: {format_tonnes(float(row.Value))}"
        for row in leaders.itertuples(index=False)
    ) or "No comparison rows"

    return "\n".join(
        [
            f"Dashboard country: {country}",
            f"Countries to compare: {', '.join(context_areas)}",
            f"Crops to compare: {', '.join(context_items) or 'None'}",
            f"Selected crops on dashboard: {', '.join(selected_items) or 'None'}",
            f"Selected year range: {year_range[0]}-{year_range[1]}",
            f"Year used for the map and country rankings: {comparison_year}",
            f"Country crop values for {latest_year}: {top_crops}",
            f"Top countries for selected crops in {comparison_year}: {top_countries}",
            f"Data source note: {source_note}",
        ]
    )


def build_context_areas(data: pd.DataFrame, selected_country: str, question: str) -> list[str]:
    areas = [selected_country]
    question_text = question.casefold()
    for area in sorted(data["Area"].dropna().unique(), key=len, reverse=True):
        area_text = str(area)
        if area_text.casefold() in question_text and area_text not in areas:
            areas.append(area_text)
    return areas


def build_context_items(data: pd.DataFrame, selected_items: list[str], question: str) -> list[str]:
    items = list(selected_items)
    question_text = question.casefold()
    for item in sorted(data["Item"].dropna().unique(), key=len, reverse=True):
        item_text = str(item)
        if item_text.casefold() in question_text and item_text not in items:
            items.append(item_text)
    return items


def ask_groq(question: str, context: str, api_key: str, model: str) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an agricultural data assistant inside a FAOSTAT dashboard. "
                    "Answer using the provided dashboard context. If the context is not enough, "
                    "say what extra filter or data would be needed. Keep answers concise."
                ),
            },
            {"role": "user", "content": f"Dashboard context:\n{context}\n\nQuestion: {question}"},
        ],
        "temperature": 0.2,
    }
    response = requests.post(GROQ_CHAT_COMPLETIONS_URL, headers=headers, json=payload, timeout=45)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def get_secret_value(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.getenv(name, default))


def summarize_filter_state(
    country: str,
    selected_group: str,
    selected_items: list[str],
    year_range: tuple[int, int],
    is_live: bool,
) -> str:
    crop_label = f"{len(selected_items)} crop" if len(selected_items) == 1 else f"{len(selected_items)} crops"
    return f"{country} | {selected_group} | {crop_label} | {year_range[0]}-{year_range[1]}"


def build_crop_tile_options(data: pd.DataFrame, selected_items: list[str], limit: int = 18) -> list[str]:
    top_items = (
        data.groupby("Item")["Value"]
        .sum()
        .sort_values(ascending=False)
        .head(limit)
        .index.tolist()
    )
    options = list(top_items)
    for item in selected_items:
        if item not in options:
            options.append(item)
    return options


def growth_percentage(start_value: float, end_value: float) -> float | None:
    if start_value == 0:
        return None
    return round(((end_value - start_value) / start_value) * 100, 1)


def build_country_comparison(
    data: pd.DataFrame,
    country_a: str,
    country_b: str,
    crop: str,
    year_range: tuple[int, int],
) -> dict:
    comparison_data = data[
        data["Area"].isin([country_a, country_b])
        & data["Item"].eq(crop)
        & data["Year"].between(year_range[0], year_range[1])
    ].copy()

    if comparison_data.empty:
        return {
            "data": comparison_data,
            "latest_year": year_range[1],
            "leaders": [],
            "gap": 0,
        }

    latest_year = int(comparison_data["Year"].max())
    leaders = []
    for country in [country_a, country_b]:
        country_rows = comparison_data[comparison_data["Area"].eq(country)].sort_values("Year")
        if country_rows.empty:
            leaders.append(
                {
                    "country": country,
                    "start_value": 0,
                    "latest_value": 0,
                    "growth_pct": None,
                }
            )
            continue

        start_value = float(country_rows.iloc[0]["Value"])
        latest_value = float(country_rows.iloc[-1]["Value"])
        leaders.append(
            {
                "country": country,
                "start_value": start_value,
                "latest_value": latest_value,
                "growth_pct": growth_percentage(start_value, latest_value),
            }
        )

    leaders = sorted(leaders, key=lambda row: row["latest_value"], reverse=True)
    gap = abs(leaders[0]["latest_value"] - leaders[1]["latest_value"]) if len(leaders) == 2 else 0
    return {
        "data": comparison_data,
        "latest_year": latest_year,
        "leaders": leaders,
        "gap": gap,
    }


def build_executive_insights(
    country: str,
    latest_year: int,
    top_latest: pd.DataFrame,
    total_latest: float,
    country_totals: pd.DataFrame,
    selected_items: list[str],
    filtered: pd.DataFrame | None = None,
    year_range: tuple[int, int] | None = None,
) -> list[str]:
    if top_latest.empty:
        return [
            "No crop rows match the current filters.",
            "Try selecting a broader crop group or year range.",
            "The map and rankings will update once data is available.",
        ]

    leading_crop = top_latest.iloc[0]
    leading_value = float(leading_crop["Value"])
    leading_share = (leading_value / total_latest) * 100 if total_latest else 0
    leader_text = (
        f"{leading_crop['Item']} drives {leading_share:.1f}% of {country}'s selected-crop total "
        f"in {latest_year} ({format_tonnes(leading_value)})."
    )

    if country_totals.empty:
        rank_text = "There is not enough country ranking data for the selected year."
    else:
        ranked = country_totals.reset_index(drop=True).copy()
        ranked["Rank"] = ranked.index + 1
        country_match = ranked[ranked["Area"].eq(country)]
        global_total = float(ranked["Value"].sum())
        if not country_match.empty:
            row = country_match.iloc[0]
            country_share = (float(row["Value"]) / global_total) * 100 if global_total else 0
            rank_text = (
                f"{country} ranks #{int(row['Rank'])} among the visible countries for these crops, "
                f"with {country_share:.1f}% of their combined output."
            )
        else:
            top_country = ranked.iloc[0]
            rank_text = (
                f"{top_country['Area']} leads the visible country ranking in {latest_year} "
                f"with {format_tonnes(float(top_country['Value']))}."
            )

    total_text = build_growth_insight(country, total_latest, filtered, year_range)
    return [leader_text, rank_text, total_text]


def build_insight_facts(
    country: str,
    latest_year: int,
    top_latest: pd.DataFrame,
    total_latest: float,
    country_totals: pd.DataFrame,
    selected_items: list[str],
    filtered: pd.DataFrame | None,
    year_range: tuple[int, int],
) -> dict:
    fallback = build_executive_insights(
        country=country,
        latest_year=latest_year,
        top_latest=top_latest,
        total_latest=total_latest,
        country_totals=country_totals,
        selected_items=selected_items,
        filtered=filtered,
        year_range=year_range,
    )

    leading_crop = None
    if not top_latest.empty:
        leading_row = top_latest.iloc[0]
        leading_value = float(leading_row["Value"])
        leading_crop = {
            "crop": str(leading_row["Item"]),
            "value_tonnes": leading_value,
            "formatted_value": format_tonnes(leading_value),
            "share_of_selected_total_pct": round((leading_value / total_latest) * 100, 1) if total_latest else 0,
        }

    rank = None
    if not country_totals.empty:
        ranked = country_totals.reset_index(drop=True).copy()
        ranked["Rank"] = ranked.index + 1
        country_match = ranked[ranked["Area"].eq(country)]
        if not country_match.empty:
            row = country_match.iloc[0]
            visible_total = float(ranked["Value"].sum())
            rank = {
                "rank": int(row["Rank"]),
                "visible_country_count": int(len(ranked)),
                "value_tonnes": float(row["Value"]),
                "share_of_visible_total_pct": round((float(row["Value"]) / visible_total) * 100, 1)
                if visible_total
                else 0,
            }

    growth = None
    if filtered is not None and not filtered.empty:
        yearly = filtered.groupby("Year", as_index=False)["Value"].sum().sort_values("Year")
        if len(yearly) >= 2:
            start = yearly.iloc[0]
            end = yearly.iloc[-1]
            growth = {
                "start_year": int(start["Year"]),
                "end_year": int(end["Year"]),
                "start_value_tonnes": float(start["Value"]),
                "end_value_tonnes": float(end["Value"]),
                "growth_pct": growth_percentage(float(start["Value"]), float(end["Value"])),
            }

    return {
        "country": country,
        "year_range": [year_range[0], year_range[1]],
        "latest_year": latest_year,
        "selected_crops": selected_items,
        "selected_total_tonnes": total_latest,
        "formatted_selected_total": format_tonnes(total_latest),
        "leading_crop": leading_crop,
        "country_rank": rank,
        "growth": growth,
        "fallback_insights": fallback,
    }


def parse_llm_insights(content: str) -> list[str]:
    numbered_insights = []
    for line in content.splitlines():
        match = re.match(r"^\s*\d+[\.)]\s+(.+)$", line.strip())
        if match:
            cleaned = match.group(1).strip()
            if cleaned:
                numbered_insights.append(cleaned)
        if len(numbered_insights) == 3:
            return numbered_insights

    insights = []
    for line in content.splitlines():
        cleaned = re.sub(r"^\s*[-*\d.)]+\s*", "", line).strip()
        lowered = cleaned.casefold()
        is_heading = (
            lowered.startswith("here are")
            or lowered in {"executive insights:", "insights:", "three insights:"}
            or ("insight" in lowered and cleaned.endswith(":"))
        )
        if cleaned and not is_heading:
            insights.append(cleaned)
        if len(insights) == 3:
            break
    return insights


def generate_llm_insights(
    facts: dict,
    api_key: str,
    model: str,
    fallback_insights: list[str],
) -> list[str]:
    if not api_key:
        return fallback_insights

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a senior analytics storyteller for an agriculture dashboard. "
                    "Write exactly three concise, plain-English executive insights. "
                    "Return only a numbered list with items 1, 2, and 3. "
                    "Do not write an introduction, title, heading, summary, or sign-off. "
                    "Use only the supplied facts. Do not invent numbers. "
                    "Each insight must explain why the number matters, not just repeat it."
                ),
            },
            {"role": "user", "content": f"Facts:\n{facts}"},
        ],
        "temperature": 0.15,
    }
    try:
        response = requests.post(
            GROQ_CHAT_COMPLETIONS_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=45,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        insights = parse_llm_insights(content)
        return insights if len(insights) == 3 else fallback_insights
    except Exception:
        return fallback_insights


def build_growth_insight(
    country: str,
    total_latest: float,
    filtered: pd.DataFrame | None,
    year_range: tuple[int, int] | None,
) -> str:
    if filtered is None or filtered.empty or year_range is None:
        return f"The selected crops add up to {format_tonnes(total_latest)} for {country}."

    yearly = filtered.groupby("Year", as_index=False)["Value"].sum().sort_values("Year")
    if len(yearly) < 2:
        return f"The selected crops add up to {format_tonnes(total_latest)} for {country}."

    start = yearly.iloc[0]
    end = yearly.iloc[-1]
    growth = growth_percentage(float(start["Value"]), float(end["Value"]))
    if growth is None:
        return (
            f"Production is {format_tonnes(float(end['Value']))} in {int(end['Year'])}; "
            f"growth cannot be calculated from a zero starting value."
        )

    direction = "increased" if growth >= 0 else "decreased"
    return (
        f"From {int(start['Year'])} to {int(end['Year'])}, {country}'s selected-crop total "
        f"{direction} by {growth:+.1f}%."
    )


def build_suggested_questions(
    country: str,
    selected_items: list[str],
    year_range: tuple[int, int],
) -> list[str]:
    crop = selected_items[0] if selected_items else "the selected crops"
    return [
        f"What is the main insight for {country} from {year_range[0]} to {year_range[1]}?",
        f"Is {country} growing more {crop} over time?",
        f"Which countries grow the most {crop} in {year_range[1]}?",
        f"What changed most in {country}'s selected crops?",
    ]


def inject_dashboard_css() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.8rem;
            padding-bottom: 2rem;
            max-width: 1500px;
        }
        h1 {
            margin-bottom: 0.15rem;
            letter-spacing: 0;
        }
        div[data-testid="stVerticalBlock"] {
            gap: 0.7rem;
        }
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e7e2d5;
            border-radius: 8px;
            padding: 0.8rem 0.9rem;
            box-shadow: 0 1px 2px rgba(20, 20, 20, 0.04);
        }
        .view-bar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            padding: 0.75rem 0.9rem;
            border: 1px solid #e7e2d5;
            border-radius: 8px;
            background: #ffffff;
        }
        .view-label {
            color: #77746b;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 0.15rem;
        }
        .view-summary {
            font-size: 1rem;
            color: #2f302c;
            font-weight: 600;
        }
        .section-note {
            color: #77746b;
            font-size: 0.92rem;
            margin-top: -0.35rem;
        }
        .insight-card {
            min-height: 96px;
            padding: 0.9rem 1rem;
            border: 1px solid #e7e2d5;
            border-radius: 8px;
            background: #ffffff;
            box-shadow: 0 1px 2px rgba(20, 20, 20, 0.04);
        }
        .insight-label {
            color: #77746b;
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.35rem;
        }
        .insight-copy {
            color: #2f302c;
            font-size: 0.98rem;
            line-height: 1.35;
            font-weight: 600;
        }
        div[data-testid="stTabs"] button {
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    data, is_live, source_note = load_faostat_qcl()

    inject_dashboard_css()

    st.title("What Countries Grow Across the Years")
    st.caption(
        "Crop production quantities from FAOSTAT's Crops and livestock products domain (QCL)."
    )

    countries = sorted(data["Area"].dropna().unique())
    if not countries:
        st.error("No country data is available. Try refreshing the app.")
        st.stop()

    default_country = "United Kingdom" if "United Kingdom" in countries else countries[0]
    country = st.session_state.get("country", default_country)
    country_data = data[data["Area"].eq(country)]
    items = sorted(country_data["Item"].dropna().unique())
    selected_group = st.session_state.get("selected_group", "All crops")
    group_choices = group_options(items)
    if selected_group not in group_choices:
        selected_group = "All crops"
    grouped_country_data = apply_group_filter(country_data, selected_group)
    available_items = sorted(grouped_country_data["Item"].dropna().unique())
    default_items = (
        grouped_country_data.groupby("Item")["Value"]
        .sum()
        .sort_values(ascending=False)
        .head(6)
        .index.tolist()
    )
    selected_items = st.session_state.get("selected_items", default_items)
    selected_items = [item for item in selected_items if item in available_items] or default_items

    min_year = int(data["Year"].min())
    max_year = int(data["Year"].max())
    year_range = st.session_state.get("year_range", (max(min_year, max_year - 20), max_year))
    map_year = year_range[1]

    view_summary = summarize_filter_state(country, selected_group, selected_items, year_range, is_live)
    st.markdown(
        f"""
        <div class="view-bar">
            <div>
                <div class="view-label">Current view</div>
                <div class="view-summary">{escape(view_summary)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        country_col, year_col = st.columns([1, 2])
        with country_col:
            country = st.selectbox(
                "Country",
                countries,
                index=countries.index(country) if country in countries else countries.index(default_country),
                key="country",
                help=f"{len(countries):,} countries and FAOSTAT areas loaded.",
            )
        with year_col:
            year_range = st.slider(
                "Year range",
                min_year,
                max_year,
                year_range,
                key="year_range",
            )
            map_year = year_range[1]

        country_data = data[data["Area"].eq(country)]
        items = sorted(country_data["Item"].dropna().unique())
        group_choices = group_options(items)
        if selected_group not in group_choices:
            selected_group = "All crops"
        selected_group = st.segmented_control(
            "Crop group",
            group_choices,
            default=selected_group,
            selection_mode="single",
            key="selected_group",
            width="stretch",
        ) or "All crops"
        grouped_country_data = apply_group_filter(country_data, selected_group)
        available_items = sorted(grouped_country_data["Item"].dropna().unique())
        default_items = (
            grouped_country_data.groupby("Item")["Value"]
            .sum()
            .sort_values(ascending=False)
            .head(6)
            .index.tolist()
        )
        tile_options = build_crop_tile_options(grouped_country_data, selected_items, limit=18)
        selected_items = st.pills(
            "Crops",
            tile_options,
            selection_mode="multi",
            default=[item for item in selected_items if item in tile_options] or default_items[:6],
            key="selected_items",
            width="stretch",
            help="Click crops to add or remove them from the map, charts, and rankings.",
        )
        selected_items = [item for item in selected_items if item in available_items] or default_items

    filtered = grouped_country_data[
        grouped_country_data["Item"].isin(selected_items)
        & grouped_country_data["Year"].between(year_range[0], year_range[1])
    ]

    latest_year = int(filtered["Year"].max()) if not filtered.empty else map_year
    latest = filtered[filtered["Year"].eq(latest_year)]
    top_latest = latest.groupby("Item", as_index=False)["Value"].sum().sort_values("Value", ascending=False)
    total_latest = float(top_latest["Value"].sum()) if not top_latest.empty else 0

    map_data = build_top_crop_map_data(data, selected_items, map_year)
    comparison = data[
        data["Item"].isin(selected_items)
        & data["Year"].eq(map_year)
    ]
    country_totals = (
        comparison.groupby("Area", as_index=False)["Value"]
        .sum()
        .sort_values("Value", ascending=False)
        .head(20)
    )

    metric_cols = st.columns(3)
    metric_cols[0].metric("Country", country)
    metric_cols[1].metric("Crops", len(selected_items))
    metric_cols[2].metric(f"Total in {latest_year}", format_tonnes(total_latest))

    groq_model = get_secret_value("GROQ_MODEL", DEFAULT_GROQ_MODEL)
    groq_api_key = get_secret_value("GROQ_API_KEY")
    insight_facts = build_insight_facts(
        country=country,
        latest_year=latest_year,
        top_latest=top_latest,
        total_latest=total_latest,
        country_totals=country_totals,
        selected_items=selected_items,
        filtered=filtered,
        year_range=year_range,
    )
    insights = generate_llm_insights(
        insight_facts,
        groq_api_key,
        groq_model,
        insight_facts["fallback_insights"],
    )
    insight_cols = st.columns(3)
    for index, insight in enumerate(insights):
        with insight_cols[index]:
            st.markdown(
                f"""
                <div class="insight-card">
                    <div class="insight-label">Insight {index + 1}</div>
                    <div class="insight-copy">{escape(insight)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    map_tab, compare_tab, overview_tab, trends_tab, countries_tab, assistant_tab = st.tabs(
        ["World Map", "Compare Countries", "Overview", "Trends", "Countries", "AI Assistant"]
    )

    with overview_tab:
        summary_col, table_col = st.columns([2, 1])
        with summary_col:
            st.subheader("Snapshot")
            if top_latest.empty:
                st.info("No crop production rows match the current filters.")
            else:
                leading_crop = top_latest.iloc[0]
                st.markdown(
                    f"In **{latest_year}**, the biggest crop shown for **{country}** is "
                    f"**{leading_crop['Item']}** "
                    f"({format_tonnes(float(leading_crop['Value']))})."
                )
                st.caption(
                    "Use the tabs above to switch between the map, country trend lines, ranked producers, and AI help."
                )
        with table_col:
            st.subheader(f"Top Crops, {latest_year}")
            st.dataframe(
                top_latest.assign(Value=top_latest["Value"].map(format_tonnes)),
                width="stretch",
                hide_index=True,
            )

    with map_tab:
        st.subheader(f"Top Selected Crop by Country, {map_year}")
        st.markdown(
            "<div class=\"section-note\">Each country is colored by the biggest selected crop it grows in the final year of your range.</div>",
            unsafe_allow_html=True,
        )
        if map_data.empty:
            st.info("No map data for the selected crops and selected end year.")
        else:
            fig = px.choropleth(
                map_data,
                locations="Area",
                locationmode="country names",
                color="Item",
                hover_name="Area",
                hover_data={
                    "Item": True,
                    "ValueLabel": True,
                    "Area": False,
                    "Value": False,
                },
                projection="natural earth",
                labels={"Item": "Top crop", "ValueLabel": "Production"},
            )
            fig.update_layout(
                height=620,
                margin=dict(l=8, r=8, t=8, b=8),
                legend_title_text="Top crop",
            )
            st.plotly_chart(fig, width="stretch")

    with trends_tab:
        st.subheader(f"{country} Crop Production Trends")
        if filtered.empty:
            st.info("No data for the current filters.")
        else:
            fig = px.line(
                filtered,
                x="Year",
                y="Value",
                color="Item",
                markers=True,
                labels={"Value": "Production quantity (tonnes)", "Item": "Crop"},
            )
            fig.update_layout(legend_title_text="Crop", hovermode="x unified", margin=dict(l=8, r=8, t=20, b=8))
            st.plotly_chart(fig, width="stretch")

    with compare_tab:
        st.subheader("Compare Two Countries")
        st.markdown(
            "<div class=\"section-note\">Choose two countries and one crop to see who grows more and how both changed over time.</div>",
            unsafe_allow_html=True,
        )
        compare_control_cols = st.columns([1, 1, 1])
        default_a = country if country in countries else default_country
        default_b = "India" if default_a != "India" and "India" in countries else "Japan"
        if default_b not in countries or default_b == default_a:
            default_b = next((candidate for candidate in countries if candidate != default_a), default_a)

        with compare_control_cols[0]:
            country_a = st.selectbox(
                "Country A",
                countries,
                index=countries.index(default_a),
                key="compare_country_a",
            )
        with compare_control_cols[1]:
            country_b = st.selectbox(
                "Country B",
                countries,
                index=countries.index(default_b),
                key="compare_country_b",
            )

        common_crops = sorted(
            set(data[data["Area"].eq(country_a)]["Item"].dropna().unique())
            & set(data[data["Area"].eq(country_b)]["Item"].dropna().unique())
        )
        with compare_control_cols[2]:
            if common_crops:
                preferred_crop = "Rice" if "Rice" in common_crops else common_crops[0]
                compare_crop = st.selectbox(
                    "Crop",
                    common_crops,
                    index=common_crops.index(preferred_crop),
                    key="compare_crop",
                )
            else:
                compare_crop = ""
                st.info("These two countries do not share crop data in this dataset.")

        if compare_crop:
            comparison_result = build_country_comparison(data, country_a, country_b, compare_crop, year_range)
            compare_data = comparison_result["data"]
            leaders = comparison_result["leaders"]
            if compare_data.empty or len(leaders) < 2:
                st.info("No comparison data is available for this crop and year range.")
            else:
                leader = leaders[0]
                runner_up = leaders[1]
                insight_cols = st.columns(4)
                insight_cols[0].metric(
                    f"{leader['country']} in {comparison_result['latest_year']}",
                    format_tonnes(leader["latest_value"]),
                )
                insight_cols[1].metric(
                    f"{runner_up['country']} in {comparison_result['latest_year']}",
                    format_tonnes(runner_up["latest_value"]),
                )
                insight_cols[2].metric("Production gap", format_tonnes(comparison_result["gap"]))
                growth_text = "n/a" if leader["growth_pct"] is None else f"{leader['growth_pct']:+.1f}%"
                insight_cols[3].metric(f"{leader['country']} growth", growth_text)

                st.markdown(
                    f"**{leader['country']}** grows more **{compare_crop}** than **{runner_up['country']}** "
                    f"in **{comparison_result['latest_year']}**, by **{format_tonnes(comparison_result['gap'])}**."
                )
                compare_fig = px.line(
                    compare_data,
                    x="Year",
                    y="Value",
                    color="Area",
                    markers=True,
                    labels={"Value": "Production quantity (tonnes)", "Area": "Country"},
                )
                compare_fig.update_layout(
                    height=520,
                    legend_title_text="Country",
                    hovermode="x unified",
                    margin=dict(l=8, r=8, t=20, b=8),
                )
                st.plotly_chart(compare_fig, width="stretch")

    with countries_tab:
        st.subheader(f"Top Producing Countries, {map_year}")
        if country_totals.empty:
            st.info("No country ranking data for the selected crops and selected end year.")
        else:
            fig = px.bar(
                country_totals,
                x="Value",
                y="Area",
                orientation="h",
                labels={"Value": "Production quantity (tonnes)", "Area": "Country"},
            )
            fig.update_layout(yaxis={"categoryorder": "total ascending"}, margin=dict(l=8, r=8, t=10, b=8))
            st.plotly_chart(fig, width="stretch")
            st.dataframe(
                country_totals.assign(Value=country_totals["Value"].map(format_tonnes)),
                width="stretch",
                hide_index=True,
            )

    with assistant_tab:
        st.subheader("Ask About This Dashboard")
        st.caption("Ask about the selected country, crops, map, rankings, or trends.")
        suggested_questions = build_suggested_questions(country, selected_items, year_range)
        suggestion = st.pills(
            "Suggested questions",
            suggested_questions,
            selection_mode="single",
            key="suggested_question",
            width="stretch",
        )
        question = st.text_area(
            "Question",
            value=suggestion or "",
            placeholder="Example: Which selected crop dominates South America in the selected end year?",
            height=96,
        )
        if st.button("Ask AI Assistant", type="primary"):
            if not question.strip():
                st.warning("Enter a question first.")
            elif not groq_api_key:
                st.warning("The AI assistant is not configured yet. Add GROQ_API_KEY in Streamlit secrets.")
            else:
                context = build_assistant_context(
                    data=data,
                    country=country,
                    selected_items=selected_items,
                    year_range=year_range,
                    comparison_year=map_year,
                    source_note=source_note,
                    question=question,
                )
                with st.spinner("Asking AI assistant..."):
                    try:
                        answer = ask_groq(question, context, groq_api_key, groq_model)
                        st.markdown(answer)
                    except requests.HTTPError as exc:
                        st.error(f"AI assistant request failed: {exc.response.status_code} {exc.response.text}")
                    except Exception as exc:
                        st.error(f"AI assistant failed: {exc}")

    st.caption(
        f"Source: {source_note}. FAOSTAT QCL: https://www.fao.org/faostat/en/#data/QCL"
    )


if __name__ == "__main__":
    main()
