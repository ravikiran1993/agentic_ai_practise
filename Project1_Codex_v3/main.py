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
# Gemini is the primary provider (generous free daily request budget); Groq is an
# automatic fallback. Both expose an OpenAI-compatible /chat/completions endpoint,
# so the same request/response shape works for either.
GEMINI_CHAT_COMPLETIONS_URL = (
    "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
)
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
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
CHART_COLORS = ["#ccff5a", "#6b8cff", "#43d4b7", "#ffb454", "#ff6f91", "#9fe870", "#76d0ff"]
CHART_BACKGROUND = "#121826"
PANEL_BACKGROUND = "#182133"

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

    # Year-by-year series so the model can actually answer trend / "what changed"
    # questions across the selected range, not just the single latest year.
    country_scoped = scoped[scoped["Area"].eq(country)]
    country_yearly = (
        country_scoped.groupby("Year", as_index=False)["Value"].sum().sort_values("Year")
    )
    yearly_trend = ", ".join(
        f"{int(row.Year)}: {format_tonnes(float(row.Value))}"
        for row in country_yearly.itertuples(index=False)
    ) or "No yearly data"

    crop_changes = []
    for item in context_items:
        item_yearly = (
            country_scoped[country_scoped["Item"].eq(item)]
            .groupby("Year", as_index=False)["Value"]
            .sum()
            .sort_values("Year")
        )
        if item_yearly.empty:
            continue
        first = item_yearly.iloc[0]
        last = item_yearly.iloc[-1]
        crop_changes.append(
            f"{item}: {int(first['Year'])} {format_tonnes(float(first['Value']))} -> "
            f"{int(last['Year'])} {format_tonnes(float(last['Value']))}"
        )
    crop_change_text = "; ".join(crop_changes) or "No per-crop trend data"

    return "\n".join(
        [
            f"Dashboard country: {country}",
            f"Countries to compare: {', '.join(context_areas)}",
            f"Crops to compare: {', '.join(context_items) or 'None'}",
            f"Selected crops on dashboard: {', '.join(selected_items) or 'None'}",
            f"Selected year range: {year_range[0]}-{year_range[1]}",
            f"Year used for the map and country rankings: {comparison_year}",
            f"Country crop values for {latest_year}: {top_crops}",
            f"{country} total of selected crops per year ({year_range[0]}-{year_range[1]}): {yearly_trend}",
            f"{country} per-crop change across the range: {crop_change_text}",
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


def build_ai_providers() -> list[dict]:
    """Ordered list of configured LLM providers: Gemini first, Groq as fallback.

    Each entry is OpenAI-compatible, so they share the same request shape. A
    provider is only included when its API key is present, so the assistant works
    with either key alone, or uses Groq automatically when Gemini fails.
    """
    providers: list[dict] = []
    gemini_key = get_secret_value("GEMINI_API_KEY")
    if gemini_key:
        providers.append(
            {
                "name": "Gemini",
                "url": GEMINI_CHAT_COMPLETIONS_URL,
                "api_key": gemini_key,
                "model": get_secret_value("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
            }
        )
    groq_key = get_secret_value("GROQ_API_KEY")
    if groq_key:
        providers.append(
            {
                "name": "Groq",
                "url": GROQ_CHAT_COMPLETIONS_URL,
                "api_key": groq_key,
                "model": get_secret_value("GROQ_MODEL", DEFAULT_GROQ_MODEL),
            }
        )
    return providers


def chat_completion(providers: list[dict], messages: list[dict], temperature: float) -> str:
    """Call each provider in order until one succeeds; raise the last error if all fail."""
    last_error: Exception | None = None
    for provider in providers:
        if not provider.get("api_key"):
            continue
        try:
            response = requests.post(
                provider["url"],
                headers={
                    "Authorization": f"Bearer {provider['api_key']}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": provider["model"],
                    "messages": messages,
                    "temperature": temperature,
                },
                timeout=45,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:  # try the next provider (e.g. Gemini rate limit -> Groq)
            last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError("No AI provider is configured.")


def ask_assistant(question: str, context: str, providers: list[dict]) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "You are an agricultural data assistant inside a FAOSTAT dashboard. "
                "Answer using the provided dashboard context. If the context is not enough, "
                "say what extra filter or data would be needed. Keep answers concise."
            ),
        },
        {"role": "user", "content": f"Dashboard context:\n{context}\n\nQuestion: {question}"},
    ]
    return chat_completion(providers, messages, 0.2)


def friendly_ai_error(exc: requests.HTTPError) -> str:
    status_code = exc.response.status_code if exc.response is not None else None
    if status_code == 429:
        return (
            "The AI assistant has reached today's usage limit on every configured provider. "
            "Please try again later, or add a Gemini/Groq key with more daily capacity."
        )
    if status_code in {401, 403}:
        return "The AI assistant key is not authorized. Please check your GEMINI_API_KEY / GROQ_API_KEY in Streamlit secrets."
    if status_code is not None:
        return f"The AI assistant could not answer right now. The provider returned status {status_code}."
    return "The AI assistant could not answer right now. Please try again."


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


def default_selection_for_context(data: pd.DataFrame, selected_items: list[str] | None = None) -> list[str]:
    return build_crop_tile_options(data, selected_items or [], limit=18)


def simplify_crop_label(item: str) -> str:
    label = str(item)
    replacements = {
        "Cereals, primary": "Cereals",
        "Fruit Primary": "Fruit",
        "Vegetables Primary": "Vegetables",
        "Roots and Tubers, Total": "Root crops",
        "Milk, Total": "Milk",
        "Meat, Total": "Meat",
        "Raw milk of cattle": "Cattle milk",
        "Raw milk of sheep": "Sheep milk",
        "Skim milk of cows": "Skim milk",
        "Other vegetables, fresh n.e.c.": "Other vegetables",
        "Maize (corn)": "Maize",
        "Onions and shallots, dry (excluding dehydrated)": "Onions",
    }
    if label in replacements:
        return replacements[label]

    label = re.sub(r",?\s*primary$", "", label, flags=re.IGNORECASE)
    label = re.sub(r",?\s*total$", "", label, flags=re.IGNORECASE)
    label = label.replace(" n.e.c.", "")
    label = label.replace(" (excluding dehydrated)", "")
    return label.strip()


def crop_icon(item: str) -> str:
    item_text = str(item).casefold()
    specific_icons = [
        (["grape"], "\U0001f347"),
        (["apple"], "\U0001f34e"),
        (["orange"], "\U0001f34a"),
        (["watermelon"], "\U0001f349"),
        (["banana"], "\U0001f34c"),
        (["pineapple"], "\U0001f34d"),
        (["strawberry"], "\U0001f353"),
        (["maize", "corn"], "\U0001f33d"),
        (["rice"], "\U0001f35a"),
        (["wheat", "barley", "cereal", "oats", "rye", "sorghum", "millet"], "\U0001f33e"),
        (["potato", "tuber"], "\U0001f954"),
        (["onion", "shallot"], "\U0001f9c5"),
        (["tomato"], "\U0001f345"),
        (["carrot", "root"], "\U0001f955"),
        (["pepper"], "\U0001fad1"),
        (["milk", "cattle", "sheep", "cow"], "\U0001f95b"),
        (["meat"], "\U0001f969"),
        (["coffee"], "\u2615"),
        (["cocoa"], "\U0001f36b"),
        (["tea"], "\U0001fad6"),
        (["cotton"], "\U0001f9f5"),
    ]
    for keywords, icon in specific_icons:
        if any(keyword in item_text for keyword in keywords):
            return icon

    if "fruit" in item_text:
        return "\U0001f34e"
    if "vegetable" in item_text:
        return "\U0001f96c"
    return "\U0001f331"


def format_crop_option(item: str) -> str:
    return f"{crop_icon(item)} {simplify_crop_label(item)}"


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
    providers: list[dict],
    fallback_insights: list[str],
) -> list[str]:
    if not providers:
        return fallback_insights

    messages = [
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
    ]
    try:
        content = chat_completion(providers, messages, 0.15)
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


def apply_chart_theme(fig, height: int | None = None) -> None:
    layout = {
        "template": "plotly_dark",
        "paper_bgcolor": CHART_BACKGROUND,
        "plot_bgcolor": CHART_BACKGROUND,
        "font": {"color": "#f5f7ef", "family": "Inter, Segoe UI, sans-serif"},
        "colorway": CHART_COLORS,
        "legend": {
            "bgcolor": "rgba(12, 18, 30, 0.94)",
            "bordercolor": "rgba(213, 226, 214, 0.28)",
            "borderwidth": 1,
            "font": {"color": "#f5f7ef", "size": 14},
            "title": {"font": {"color": "#f5f7ef", "size": 16}},
        },
        "margin": {"l": 10, "r": 10, "t": 24, "b": 10},
    }
    if height is not None:
        layout["height"] = height
    fig.update_layout(**layout)
    fig.update_xaxes(gridcolor="rgba(156, 176, 204, 0.12)", zerolinecolor="rgba(156, 176, 204, 0.16)")
    fig.update_yaxes(gridcolor="rgba(156, 176, 204, 0.12)", zerolinecolor="rgba(156, 176, 204, 0.16)")


def inject_dashboard_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700;800;900&display=swap');
        :root {
            --bg: #090d16;
            --panel: #141c2b;
            --panel-2: #192437;
            --line: rgba(156, 176, 204, 0.18);
            --text: #f5f7ef;
            --muted: #a8b0bd;
            --lime: #ccff5a;
            --green: #43d477;
            --blue: #6b8cff;
            --cyan: #43d4b7;
            --danger: #ff7f84;
        }
        html, body, [class*="css"] {
            font-family: Inter, "Segoe UI", sans-serif;
        }
        .stApp {
            color: var(--text);
            background:
                radial-gradient(circle at 18% 8%, rgba(67, 212, 119, 0.2), transparent 24rem),
                radial-gradient(circle at 88% 12%, rgba(107, 140, 255, 0.22), transparent 26rem),
                linear-gradient(135deg, #080b12 0%, #0e1421 48%, #07100d 100%);
        }
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2.4rem;
            max-width: 1540px;
        }
        h1 {
            color: var(--text);
            font-size: clamp(2.2rem, 4.2vw, 4.8rem);
            font-weight: 900;
            letter-spacing: 0;
            line-height: 0.96;
            margin-bottom: 0.35rem;
            text-shadow: 0 18px 48px rgba(0, 0, 0, 0.34);
        }
        h2, h3 {
            color: var(--text);
            font-weight: 800;
            letter-spacing: 0;
        }
        p, label, span, div {
            letter-spacing: 0;
        }
        [data-testid="stCaptionContainer"], .stMarkdown p {
            color: var(--muted);
        }
        div[data-testid="stWidgetLabel"] label,
        div[data-testid="stWidgetLabel"] p {
            color: #f5f7ef !important;
            font-weight: 850 !important;
            opacity: 1 !important;
        }
        label,
        label p,
        [data-testid="stMarkdownContainer"] p {
            color: #dfe6d8;
            opacity: 1;
        }
        div[data-testid="stVerticalBlock"] {
            gap: 0.7rem;
        }
        div[data-testid="stContainer"] > div[data-testid="stVerticalBlockBorderWrapper"] {
            border: 1px solid var(--line);
            border-radius: 10px;
            background:
                linear-gradient(180deg, rgba(255, 255, 255, 0.045), rgba(255, 255, 255, 0.018)),
                rgba(20, 28, 43, 0.84);
            box-shadow: 0 18px 44px rgba(0, 0, 0, 0.24);
        }
        div[data-testid="stMetric"] {
            min-height: 136px;
            background:
                linear-gradient(150deg, rgba(204, 255, 90, 0.11), transparent 36%),
                linear-gradient(180deg, rgba(255, 255, 255, 0.062), rgba(255, 255, 255, 0.022)),
                var(--panel);
            border: 1px solid var(--line);
            border-radius: 10px;
            padding: 1.05rem 1.15rem;
            box-shadow: 0 18px 40px rgba(0, 0, 0, 0.22);
        }
        div[data-testid="stMetric"] label,
        div[data-testid="stMetric"] [data-testid="stMetricLabel"] {
            color: var(--muted);
            font-size: 0.82rem;
            text-transform: uppercase;
            font-weight: 800;
        }
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            color: var(--text);
            font-size: clamp(2rem, 3.1vw, 3.25rem);
            font-weight: 900;
        }
        .view-bar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            padding: 0.95rem 1.05rem;
            border: 1px solid var(--line);
            border-radius: 10px;
            background:
                linear-gradient(90deg, rgba(67, 212, 119, 0.12), rgba(107, 140, 255, 0.09)),
                rgba(20, 28, 43, 0.82);
            box-shadow: 0 18px 40px rgba(0, 0, 0, 0.2);
        }
        .view-label {
            color: var(--lime);
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.15rem;
            font-weight: 900;
        }
        .view-summary {
            font-size: 1rem;
            color: var(--text);
            font-weight: 750;
        }
        .section-note {
            color: var(--muted);
            font-size: 0.92rem;
            margin-top: -0.35rem;
        }
        .selected-crop-strip {
            display: flex;
            align-items: center;
            gap: 0.55rem;
            flex-wrap: wrap;
            padding: 0.7rem 0.75rem;
            border: 1px solid rgba(204, 255, 90, 0.2);
            border-radius: 10px;
            background: rgba(7, 12, 20, 0.55);
        }
        .selected-crop-label {
            color: var(--lime);
            font-size: 0.76rem;
            font-weight: 900;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }
        .selected-crop-chip {
            color: #07100c;
            padding: 0.42rem 0.68rem;
            border-radius: 999px;
            background: linear-gradient(135deg, var(--lime), var(--green));
            box-shadow: 0 10px 24px rgba(67, 212, 119, 0.2);
            font-size: 0.86rem;
            font-weight: 900;
        }
        .selected-crop-empty {
            color: #dfe6d8;
            padding: 0.42rem 0.68rem;
            border: 1px dashed rgba(156, 176, 204, 0.42);
            border-radius: 999px;
            background: rgba(17, 24, 39, 0.72);
            font-size: 0.86rem;
            font-weight: 850;
        }
        .insight-card {
            min-height: 142px;
            padding: 1rem 1.1rem;
            border: 1px solid var(--line);
            border-radius: 10px;
            background:
                linear-gradient(135deg, rgba(107, 140, 255, 0.12), transparent 34%),
                linear-gradient(180deg, rgba(255, 255, 255, 0.058), rgba(255, 255, 255, 0.02)),
                var(--panel);
            box-shadow: 0 18px 42px rgba(0, 0, 0, 0.22);
        }
        .insight-label {
            color: var(--cyan);
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.45rem;
            font-weight: 900;
        }
        .insight-copy {
            color: var(--text);
            font-size: 0.98rem;
            line-height: 1.35;
            font-weight: 750;
        }
        div[data-testid="stTabs"] {
            background: rgba(20, 28, 43, 0.72);
            border: 1px solid var(--line);
            border-radius: 10px;
            padding: 0.25rem 0.4rem 0.65rem;
            box-shadow: 0 18px 44px rgba(0, 0, 0, 0.2);
        }
        div[data-testid="stTabs"] button {
            color: var(--muted);
            font-weight: 850;
            border-radius: 8px;
            min-height: 2.7rem;
        }
        div[data-testid="stTabs"] button[aria-selected="true"] {
            color: #07100c !important;
            background: linear-gradient(135deg, var(--lime), var(--green));
        }
        div[data-testid="stTabs"] button[aria-selected="true"] *,
        div[data-testid="stTabs"] button[aria-selected="true"] p,
        div[data-testid="stTabs"] button[aria-selected="true"] span {
            color: #07100c !important;
            font-weight: 900 !important;
            opacity: 1 !important;
        }
        div[data-baseweb="select"] > div,
        div[data-testid="stTextArea"] textarea,
        div[data-testid="stTextInput"] input {
            color: var(--text) !important;
            background: rgba(7, 12, 20, 0.82) !important;
            border-color: rgba(156, 176, 204, 0.42) !important;
            border-radius: 8px;
        }
        div[data-baseweb="select"] span,
        div[data-baseweb="select"] div {
            color: var(--text) !important;
            opacity: 1 !important;
        }
        div[data-baseweb="popover"] {
            background: #111827;
        }
        div[data-baseweb="popover"] li,
        div[data-baseweb="menu"] li {
            color: var(--text);
            background: #111827;
        }
        div[data-baseweb="popover"] li:hover,
        div[data-baseweb="menu"] li:hover {
            color: #07100c;
            background: var(--lime);
        }
        div[data-baseweb="select"] svg {
            color: var(--muted);
        }
        div[data-testid="stSlider"] {
            color: var(--text) !important;
        }
        div[data-testid="stSlider"] [role="slider"] {
            border-color: var(--lime);
            background: var(--lime);
        }
        div[data-testid="stSlider"] [data-testid="stTickBar"] {
            color: #dfe6d8 !important;
        }
        div[data-testid="stSlider"] [data-testid="stThumbValue"],
        div[data-testid="stSlider"] [data-testid="stTickBar"] div {
            color: var(--lime) !important;
            font-weight: 850 !important;
            opacity: 1 !important;
        }
        .st-key-selected_group {
            background: rgba(7, 12, 20, 0.56);
            border: 1px solid rgba(156, 176, 204, 0.3);
            border-radius: 10px;
            padding: 0.18rem;
        }
        .st-key-selected_group button,
        .st-key-selected_group [role="button"] {
            color: #f5f7ef !important;
            background: #111827 !important;
            border-color: rgba(156, 176, 204, 0.34) !important;
            box-shadow: none !important;
            opacity: 1 !important;
            font-weight: 850 !important;
        }
        .st-key-selected_group button p,
        .st-key-selected_group [role="button"] p,
        .st-key-selected_group button span,
        .st-key-selected_group [role="button"] span {
            color: #f5f7ef !important;
            opacity: 1 !important;
            font-weight: 850 !important;
        }
        .st-key-selected_group button[aria-pressed="true"],
        .st-key-selected_group [role="button"][aria-pressed="true"] {
            color: #07100c !important;
            background: linear-gradient(135deg, var(--lime), var(--green)) !important;
            border-color: transparent !important;
        }
        .st-key-selected_group button[aria-pressed="true"] p,
        .st-key-selected_group [role="button"][aria-pressed="true"] p,
        .st-key-selected_group button[aria-pressed="true"] span,
        .st-key-selected_group [role="button"][aria-pressed="true"] span {
            color: #07100c !important;
        }
        div[data-testid="stSegmentedControl"] {
            background: rgba(7, 12, 20, 0.72);
            border: 1px solid rgba(156, 176, 204, 0.26);
            border-radius: 10px;
            padding: 0.12rem;
        }
        div[data-testid="stSegmentedControl"] button {
            color: #f5f7ef !important;
            background: #111827 !important;
            border-color: rgba(156, 176, 204, 0.34) !important;
            font-weight: 850 !important;
        }
        div[data-testid="stSegmentedControl"] button[aria-pressed="true"],
        div[data-testid="stSegmentedControl"] button[data-selected="true"] {
            color: #07100c !important;
            background: linear-gradient(135deg, var(--lime), var(--green)) !important;
            border-color: transparent !important;
        }
        div[data-testid="stSegmentedControl"] button p {
            color: inherit !important;
            font-weight: inherit !important;
        }
        div[data-testid="stPills"] button {
            color: #f5f7ef !important;
            background: #111827 !important;
            border: 1px solid rgba(156, 176, 204, 0.34) !important;
            font-weight: 800 !important;
        }
        div[data-testid="stPills"] button[aria-pressed="true"],
        div[data-testid="stPills"] button[data-selected="true"] {
            color: #07100c !important;
            background: linear-gradient(135deg, var(--lime), var(--green)) !important;
            border-color: transparent !important;
        }
        div[data-testid="stPills"] button p {
            color: inherit !important;
        }
        .st-key-selected_items {
            background: rgba(7, 12, 20, 0.42);
            border: 1px solid rgba(156, 176, 204, 0.18);
            border-radius: 10px;
            padding: 0.35rem;
        }
        .st-key-selected_items button,
        .st-key-selected_items [role="button"],
        .st-key-selected_items [data-testid*="stBaseButton"] {
            color: #f5f7ef !important;
            background: #111827 !important;
            border: 1px solid rgba(156, 176, 204, 0.42) !important;
            box-shadow: none !important;
            opacity: 1 !important;
            font-weight: 850 !important;
        }
        .st-key-selected_items button *,
        .st-key-selected_items [role="button"] *,
        .st-key-selected_items [data-testid*="stBaseButton"] * {
            color: #f5f7ef !important;
            opacity: 1 !important;
            font-weight: 850 !important;
        }
        .st-key-selected_items button[aria-pressed="true"],
        .st-key-selected_items button[aria-selected="true"],
        .st-key-selected_items button[aria-checked="true"],
        .st-key-selected_items button[kind="primary"],
        .st-key-selected_items [role="button"][aria-pressed="true"],
        .st-key-selected_items [role="button"][aria-selected="true"],
        .st-key-selected_items [role="button"][aria-checked="true"],
        .st-key-selected_items [role="button"][kind="primary"],
        .st-key-selected_items label:has(input:checked),
        .st-key-selected_items div:has(> input:checked) {
            color: #07100c !important;
            background: linear-gradient(135deg, var(--lime), var(--green)) !important;
            border-color: transparent !important;
            box-shadow: 0 10px 24px rgba(67, 212, 119, 0.24) !important;
        }
        .st-key-selected_items button[aria-pressed="true"] *,
        .st-key-selected_items button[aria-selected="true"] *,
        .st-key-selected_items button[aria-checked="true"] *,
        .st-key-selected_items button[kind="primary"] *,
        .st-key-selected_items [role="button"][aria-pressed="true"] *,
        .st-key-selected_items [role="button"][aria-selected="true"] *,
        .st-key-selected_items [role="button"][aria-checked="true"] *,
        .st-key-selected_items [role="button"][kind="primary"] *,
        .st-key-selected_items label:has(input:checked) *,
        .st-key-selected_items div:has(> input:checked) * {
            color: #07100c !important;
            opacity: 1 !important;
            font-weight: 900 !important;
        }
        div[data-testid="stButton"] button,
        div[data-testid="stDownloadButton"] button {
            border-radius: 8px;
            border: 1px solid rgba(204, 255, 90, 0.34);
            background: rgba(204, 255, 90, 0.08);
            color: var(--text);
            font-weight: 800;
        }
        div[data-testid="stButton"] button[kind="primary"] {
            background: linear-gradient(135deg, var(--lime), var(--green));
            color: #07100c;
            border-color: transparent;
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid var(--line);
            border-radius: 10px;
            overflow: hidden;
        }
        .st-key-floating_ai_button {
            position: fixed;
            left: 0.85rem;
            top: 48vh;
            z-index: 1002;
        }
        .st-key-floating_ai_button::before {
            content: "";
            position: absolute;
            inset: -9px;
            border-radius: 999px;
            background: radial-gradient(circle, rgba(111, 160, 85, 0.28), rgba(111, 160, 85, 0));
            animation: assistant-pulse 3.4s ease-in-out infinite;
            pointer-events: none;
        }
        .st-key-floating_ai_button::after {
            content: "Ask crop AI";
            position: absolute;
            left: 4.45rem;
            top: 50%;
            transform: translateY(-50%) translateX(-6px);
            opacity: 0;
            white-space: nowrap;
            padding: 0.45rem 0.65rem;
            border: 1px solid rgba(204, 255, 90, 0.24);
            border-radius: 999px;
            background: rgba(20, 28, 43, 0.96);
            color: var(--lime);
            box-shadow: 0 10px 26px rgba(0, 0, 0, 0.28);
            font-size: 0.82rem;
            font-weight: 750;
            transition: opacity 160ms ease, transform 160ms ease;
            pointer-events: none;
        }
        .st-key-floating_ai_button:hover::after {
            opacity: 1;
            transform: translateY(-50%) translateX(0);
        }
        .st-key-floating_ai_button button {
            border-radius: 999px;
            width: 3.9rem;
            min-width: 3.9rem;
            height: 3.9rem;
            min-height: 3.9rem;
            padding: 0;
            border: 1px solid rgba(255, 255, 255, 0.72);
            background:
                radial-gradient(circle at 34% 26%, rgba(255, 255, 255, 0.44), rgba(255, 255, 255, 0) 34%),
                linear-gradient(145deg, #89b45c 0%, #3f7d46 52%, #1f5332 100%);
            color: #ffffff;
            box-shadow:
                0 16px 34px rgba(39, 91, 48, 0.32),
                inset 0 1px 0 rgba(255, 255, 255, 0.36),
                inset 0 -8px 18px rgba(21, 67, 37, 0.24);
            font-weight: 700;
            transition: transform 160ms ease, box-shadow 160ms ease, filter 160ms ease;
        }
        .st-key-floating_ai_button button:hover {
            transform: translateY(-2px) scale(1.035);
            filter: saturate(1.06);
            box-shadow:
                0 20px 42px rgba(39, 91, 48, 0.38),
                inset 0 1px 0 rgba(255, 255, 255, 0.42),
                inset 0 -8px 18px rgba(21, 67, 37, 0.22);
        }
        .st-key-floating_ai_button button:active {
            transform: translateY(0) scale(0.98);
        }
        .st-key-floating_ai_button button p {
            display: none;
        }
        .st-key-floating_ai_button button span {
            font-size: 1.85rem;
            margin: 0;
        }
        .st-key-floating_ai_panel {
            position: fixed;
            left: 5.35rem;
            top: 24vh;
            z-index: 1001;
            width: min(430px, calc(100vw - 2rem));
            max-height: min(74vh, 680px);
            overflow-y: auto;
            padding: 1rem;
            border: 1px solid rgba(204, 255, 90, 0.18);
            border-radius: 10px;
            background:
                linear-gradient(160deg, rgba(204, 255, 90, 0.07), transparent 34%),
                rgba(20, 28, 43, 0.98);
            box-shadow: 0 18px 48px rgba(20, 20, 20, 0.2);
        }
        .assistant-kicker {
            color: var(--lime);
            font-size: 0.76rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.15rem;
        }
        .assistant-title {
            color: var(--text);
            font-size: 1.2rem;
            font-weight: 750;
            margin-bottom: 0.2rem;
        }
        .assistant-note {
            color: var(--muted);
            font-size: 0.9rem;
            line-height: 1.35;
        }
        .assistant-dock-label {
            color: var(--muted);
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-top: 0.45rem;
        }
        .st-key-floating_ai_panel .selected-crop-strip {
            margin-top: 0.65rem;
            margin-bottom: 0.7rem;
            background: rgba(7, 12, 20, 0.84);
            border-color: rgba(204, 255, 90, 0.28);
        }
        .st-key-floating_suggested_question button,
        .st-key-floating_suggested_question [role="button"],
        .st-key-floating_suggested_question [data-testid*="stBaseButton"] {
            color: #f5f7ef !important;
            background: #111827 !important;
            border: 1px solid rgba(156, 176, 204, 0.42) !important;
            box-shadow: none !important;
            opacity: 1 !important;
            font-weight: 850 !important;
            white-space: normal !important;
            min-height: 3rem;
        }
        .st-key-floating_suggested_question button *,
        .st-key-floating_suggested_question [role="button"] *,
        .st-key-floating_suggested_question [data-testid*="stBaseButton"] * {
            color: #f5f7ef !important;
            opacity: 1 !important;
            font-weight: 850 !important;
        }
        .st-key-floating_suggested_question button[aria-pressed="true"],
        .st-key-floating_suggested_question button[aria-selected="true"],
        .st-key-floating_suggested_question button[aria-checked="true"],
        .st-key-floating_suggested_question [role="button"][aria-pressed="true"],
        .st-key-floating_suggested_question [role="button"][aria-selected="true"],
        .st-key-floating_suggested_question [role="button"][aria-checked="true"] {
            color: #07100c !important;
            background: linear-gradient(135deg, var(--lime), var(--green)) !important;
            border-color: transparent !important;
        }
        .st-key-floating_suggested_question button[aria-pressed="true"] *,
        .st-key-floating_suggested_question button[aria-selected="true"] *,
        .st-key-floating_suggested_question button[aria-checked="true"] *,
        .st-key-floating_suggested_question [role="button"][aria-pressed="true"] *,
        .st-key-floating_suggested_question [role="button"][aria-selected="true"] *,
        .st-key-floating_suggested_question [role="button"][aria-checked="true"] * {
            color: #07100c !important;
            font-weight: 900 !important;
            opacity: 1 !important;
        }
        .st-key-floating_ai_panel div[data-testid="stAlert"] {
            color: #f5f7ef;
            background: rgba(68, 32, 47, 0.82);
            border: 1px solid rgba(255, 127, 132, 0.32);
            border-radius: 10px;
        }
        .st-key-floating_ai_panel div[data-testid="stAlert"] * {
            color: #f5f7ef !important;
            opacity: 1 !important;
        }
        @media (max-width: 640px) {
            .st-key-floating_ai_button {
                left: 0.75rem;
                top: 56vh;
            }
            .st-key-floating_ai_button::after {
                display: none;
            }
            .st-key-floating_ai_panel {
                left: 0.75rem;
                top: 16vh;
                width: calc(100vw - 1.5rem);
                max-height: 72vh;
            }
        }
        @keyframes assistant-pulse {
            0%, 100% {
                opacity: 0.42;
                transform: scale(0.94);
            }
            50% {
                opacity: 0.86;
                transform: scale(1.08);
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_floating_assistant(
    data: pd.DataFrame,
    country: str,
    selected_items: list[str],
    year_range: tuple[int, int],
    map_year: int,
    source_note: str,
    providers: list[dict],
) -> None:
    if "assistant_open" not in st.session_state:
        st.session_state["assistant_open"] = False
    if "assistant_dock_y" not in st.session_state:
        st.session_state["assistant_dock_y"] = 48

    dock_y = min(max(int(st.session_state.get("assistant_dock_y", 48)), 24), 76)
    st.session_state["assistant_dock_y"] = dock_y
    panel_y = min(max(dock_y - 24, 12), 38)
    st.markdown(
        f"""
        <style>
        .st-key-floating_ai_button {{
            top: {dock_y}vh;
        }}
        .st-key-floating_ai_panel {{
            top: {panel_y}vh;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    if st.button(
        "Crop AI",
        key="floating_ai_button",
        icon=":material/local_florist:",
        help="Open the AI assistant from any dashboard view.",
    ):
        st.session_state["assistant_open"] = not st.session_state["assistant_open"]

    if not st.session_state["assistant_open"]:
        return

    with st.container(key="floating_ai_panel"):
        header_cols = st.columns([1, 0.22])
        with header_cols[0]:
            st.markdown(
                """
                <div class="assistant-kicker">Dashboard assistant</div>
                <div class="assistant-title">Ask about this view</div>
                <div class="assistant-note">Uses your selected country, crops, year range, map, rankings, and trends.</div>
                """,
                unsafe_allow_html=True,
            )
        with header_cols[1]:
            if st.button("x", key="close_floating_ai", help="Close assistant"):
                st.session_state["assistant_open"] = False
                st.rerun()

        st.markdown('<div class="assistant-dock-label">Park on left edge</div>', unsafe_allow_html=True)
        st.slider(
            "Assistant position",
            min_value=24,
            max_value=76,
            value=dock_y,
            step=4,
            key="assistant_dock_y",
            label_visibility="collapsed",
            help="Move the plant assistant up or down the left edge without covering the dashboard header.",
        )

        suggested_questions = build_suggested_questions(country, selected_items, year_range)
        suggestion = st.pills(
            "Try asking",
            suggested_questions,
            selection_mode="single",
            key="floating_suggested_question",
            width="stretch",
        )
        if suggestion and suggestion != st.session_state.get("floating_last_suggestion"):
            st.session_state["floating_ai_question"] = suggestion
            st.session_state["floating_last_suggestion"] = suggestion
            st.rerun()

        question = st.text_area(
            "Question",
            key="floating_ai_question",
            placeholder="Example: Is Japan growing more rice compared with India?",
            height=92,
        )

        if st.button("Ask Assistant", type="primary", key="floating_ai_submit"):
            if not question.strip():
                st.warning("Enter a question first.")
            elif not providers:
                st.warning("Add GEMINI_API_KEY (and optionally GROQ_API_KEY) in Streamlit secrets to enable the assistant.")
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
                with st.spinner("Asking assistant..."):
                    try:
                        st.session_state["floating_ai_answer"] = ask_assistant(
                            question,
                            context,
                            providers,
                        )
                    except requests.HTTPError as exc:
                        st.error(friendly_ai_error(exc))
                    except Exception as exc:
                        st.error(f"AI assistant failed: {exc}")

        if st.session_state.get("floating_ai_answer"):
            st.markdown(st.session_state["floating_ai_answer"])


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
    previous_country = st.session_state.get("_last_country", country)
    previous_group = st.session_state.get("_last_selected_group", selected_group)
    selection_context_changed = country != previous_country or selected_group != previous_group
    if selection_context_changed:
        selected_items = default_selection_for_context(grouped_country_data)
        st.session_state["selected_items"] = selected_items
        st.session_state["_last_country"] = country
        st.session_state["_last_selected_group"] = selected_group
    elif "selected_items" in st.session_state:
        selected_items = [item for item in st.session_state["selected_items"] if item in available_items]
    else:
        selected_items = default_items
    if "_last_country" not in st.session_state:
        st.session_state["_last_country"] = country
    if "_last_selected_group" not in st.session_state:
        st.session_state["_last_selected_group"] = selected_group

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
        previous_country = st.session_state.get("_last_country", country)
        previous_group = st.session_state.get("_last_selected_group", selected_group)
        selection_context_changed = country != previous_country or selected_group != previous_group
        if selection_context_changed:
            selected_items = default_selection_for_context(grouped_country_data)
            st.session_state["selected_items"] = selected_items
        else:
            selected_items = [item for item in selected_items if item in available_items]
        st.session_state["_last_country"] = country
        st.session_state["_last_selected_group"] = selected_group

        tile_options = build_crop_tile_options(grouped_country_data, selected_items, limit=18)
        crop_action_cols = st.columns([0.16, 0.18, 0.16, 0.5])
        with crop_action_cols[0]:
            if st.button("Top 6", key="select_top_crops", help="Select the six biggest crops in this country."):
                st.session_state["selected_items"] = default_items[:6]
                st.rerun()
        with crop_action_cols[1]:
            if st.button("Select shown", key="select_shown_crops", help="Select every crop currently shown below."):
                st.session_state["selected_items"] = tile_options
                st.rerun()
        with crop_action_cols[2]:
            if st.button("Clear", key="clear_selected_crops", help="Unselect all crops."):
                st.session_state["selected_items"] = []
                st.rerun()
        default_crop_selection = (
            [item for item in selected_items if item in tile_options]
            if "selected_items" in st.session_state
            else default_items[:6]
        )
        selected_items = st.pills(
            "Crops",
            tile_options,
            selection_mode="multi",
            default=default_crop_selection,
            format_func=format_crop_option,
            key="selected_items",
            width="stretch",
            help="Click crops to add or remove them from the map, charts, and rankings.",
        )
        selected_items = [item for item in (selected_items or []) if item in available_items]
        selected_chips = (
            "".join(
                f'<span class="selected-crop-chip">{escape(format_crop_option(item))}</span>'
                for item in selected_items
            )
            or '<span class="selected-crop-empty">No crops selected</span>'
        )
        st.markdown(
            f"""
            <div class="selected-crop-strip">
                <span class="selected-crop-label">Selected crops</span>
                {selected_chips}
            </div>
            """,
            unsafe_allow_html=True,
        )

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

    providers = build_ai_providers()
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
    # Streamlit reruns the whole script on every widget interaction (slider drag,
    # tab switch, crop click). Calling the LLM here unconditionally would fire a
    # request per rerun and blow past the free-tier rate limit almost immediately.
    # So only regenerate insights when the country/crops/year-range actually change;
    # otherwise reuse the cached result for this view.
    insight_signature = (country, tuple(selected_items), tuple(year_range))
    if (
        st.session_state.get("insight_signature") == insight_signature
        and st.session_state.get("insights")
    ):
        insights = st.session_state["insights"]
    else:
        insights = generate_llm_insights(
            insight_facts,
            providers,
            insight_facts["fallback_insights"],
        )
        st.session_state["insight_signature"] = insight_signature
        st.session_state["insights"] = insights
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

    render_floating_assistant(
        data=data,
        country=country,
        selected_items=selected_items,
        year_range=year_range,
        map_year=map_year,
        source_note=source_note,
        providers=providers,
    )

    map_tab, compare_tab, overview_tab, trends_tab, countries_tab = st.tabs(
        ["World Map", "Compare Countries", "Overview", "Trends", "Countries"]
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
                    f"**{format_crop_option(leading_crop['Item'])}** "
                    f"({format_tonnes(float(leading_crop['Value']))})."
                )
                st.caption(
                    "Use the tabs above to switch between the map, country trend lines, and ranked producers. The plant assistant is available on the left."
                )
        with table_col:
            st.subheader(f"Top Crops, {latest_year}")
            st.dataframe(
                top_latest.assign(
                    Item=top_latest["Item"].map(format_crop_option),
                    Value=top_latest["Value"].map(format_tonnes),
                ),
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
            map_plot_data = map_data.assign(Crop=map_data["Item"].map(format_crop_option))
            fig = px.choropleth(
                map_plot_data,
                locations="Area",
                locationmode="country names",
                color="Crop",
                hover_name="Area",
                hover_data={
                    "Crop": True,
                    "ValueLabel": True,
                    "Area": False,
                    "Value": False,
                },
                projection="natural earth",
                labels={"Crop": "Top crop", "ValueLabel": "Production"},
                color_discrete_sequence=CHART_COLORS,
            )
            apply_chart_theme(fig, height=620)
            fig.update_layout(
                margin=dict(l=8, r=8, t=8, b=8),
                legend_title_text="Top crop",
                geo=dict(
                    bgcolor=CHART_BACKGROUND,
                    lakecolor=PANEL_BACKGROUND,
                    landcolor="#223047",
                    oceancolor="#0c1320",
                    showocean=True,
                    showcountries=True,
                    countrycolor="rgba(245, 247, 239, 0.18)",
                    coastlinecolor="rgba(245, 247, 239, 0.18)",
                ),
            )
            st.plotly_chart(fig, width="stretch")

    with trends_tab:
        st.subheader(f"{country} Crop Production Trends")
        if filtered.empty:
            st.info("No data for the current filters.")
        else:
            trend_plot_data = filtered.assign(Crop=filtered["Item"].map(format_crop_option))
            fig = px.line(
                trend_plot_data,
                x="Year",
                y="Value",
                color="Crop",
                markers=True,
                labels={"Value": "Production quantity (tonnes)", "Crop": "Crop"},
                color_discrete_sequence=CHART_COLORS,
            )
            apply_chart_theme(fig, height=540)
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
                    format_func=format_crop_option,
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
                    f"**{leader['country']}** grows more **{format_crop_option(compare_crop)}** than **{runner_up['country']}** "
                    f"in **{comparison_result['latest_year']}**, by **{format_tonnes(comparison_result['gap'])}**."
                )
                compare_fig = px.line(
                    compare_data,
                    x="Year",
                    y="Value",
                    color="Area",
                    markers=True,
                    labels={"Value": "Production quantity (tonnes)", "Area": "Country"},
                    color_discrete_sequence=CHART_COLORS,
                )
                apply_chart_theme(compare_fig, height=520)
                compare_fig.update_layout(
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
                color="Value",
                color_continuous_scale=["#223047", "#43d477", "#ccff5a"],
            )
            apply_chart_theme(fig, height=620)
            fig.update_layout(yaxis={"categoryorder": "total ascending"}, margin=dict(l=8, r=8, t=10, b=8))
            st.plotly_chart(fig, width="stretch")
            st.dataframe(
                country_totals.assign(Value=country_totals["Value"].map(format_tonnes)),
                width="stretch",
                hide_index=True,
            )

    st.caption(
        f"Source: {source_note}. FAOSTAT QCL: https://www.fao.org/faostat/en/#data/QCL"
    )


if __name__ == "__main__":
    main()
