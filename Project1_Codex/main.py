from __future__ import annotations

import os
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
) -> str:
    scoped = data[
        data["Area"].eq(country)
        & data["Item"].isin(selected_items)
        & data["Year"].between(year_range[0], year_range[1])
    ]
    latest_year = int(scoped["Year"].max()) if not scoped.empty else comparison_year
    latest = (
        scoped[scoped["Year"].eq(latest_year)]
        .groupby("Item", as_index=False)["Value"]
        .sum()
        .sort_values("Value", ascending=False)
        .head(10)
    )

    leaders = (
        data[data["Item"].isin(selected_items) & data["Year"].eq(comparison_year)]
        .groupby("Area", as_index=False)["Value"]
        .sum()
        .sort_values("Value", ascending=False)
        .head(10)
    )

    top_crops = ", ".join(
        f"{row.Item}: {format_tonnes(float(row.Value))}"
        for row in latest.itertuples(index=False)
    ) or "No selected crop rows"
    top_countries = ", ".join(
        f"{row.Area}: {format_tonnes(float(row.Value))}"
        for row in leaders.itertuples(index=False)
    ) or "No comparison rows"

    return "\n".join(
        [
            f"Dashboard country: {country}",
            f"Selected crops: {', '.join(selected_items) or 'None'}",
            f"Selected year range: {year_range[0]}-{year_range[1]}",
            f"Year used for the map and country rankings: {comparison_year}",
            f"Top selected crops in {country} for {latest_year}: {top_crops}",
            f"Top countries for selected crops in {comparison_year}: {top_countries}",
            f"Data source note: {source_note}",
        ]
    )


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


def main() -> None:
    data, is_live, source_note = load_faostat_qcl()

    st.title("What Countries Grow Across the Years")
    st.caption(
        "Crop production quantities from FAOSTAT's Crops and livestock products domain (QCL)."
    )

    countries = sorted(data["Area"].dropna().unique())
    if not countries:
        st.error("No country data is available. Try refreshing the app.")
        st.stop()

    with st.container(border=True):
        st.subheader("Filter Controls")
        country_col, group_col, crop_col = st.columns([1, 1, 2])
        default_country = "United Kingdom" if "United Kingdom" in countries else countries[0]
        with country_col:
            country = st.selectbox(
                "Country",
                countries,
                index=countries.index(default_country),
                help=f"{len(countries):,} countries, territories, and FAOSTAT regional groups loaded.",
            )

        country_data = data[data["Area"].eq(country)]
        items = sorted(country_data["Item"].dropna().unique())
        with group_col:
            selected_group = st.selectbox("Crop group", group_options(items))
        grouped_country_data = apply_group_filter(country_data, selected_group)

        available_items = sorted(grouped_country_data["Item"].dropna().unique())
        default_items = (
            grouped_country_data.groupby("Item")["Value"]
            .sum()
            .sort_values(ascending=False)
            .head(6)
            .index.tolist()
        )
        with crop_col:
            selected_items = st.multiselect("Crops", available_items, default=default_items)

        min_year = int(data["Year"].min())
        max_year = int(data["Year"].max())
        year_range = st.slider("Year range", min_year, max_year, (max(min_year, max_year - 20), max_year))
        map_year = year_range[1]

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

    overview_tab, map_tab, trends_tab, countries_tab, assistant_tab = st.tabs(
        ["Overview", "World Map", "Trends", "Countries", "AI Assistant"]
    )

    with overview_tab:
        metric_cols = st.columns(4)
        metric_cols[0].metric("Country", country)
        metric_cols[1].metric("Selected crops", len(selected_items))
        metric_cols[2].metric(f"Total in {latest_year}", format_tonnes(total_latest))
        metric_cols[3].metric("Data source", "FAOSTAT live" if is_live else "Fallback")

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
        if map_data.empty:
            st.info("No map data for the selected crops and comparison year.")
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

    with countries_tab:
        st.subheader(f"Top Producing Countries, {map_year}")
        if country_totals.empty:
            st.info("No comparison data for the selected crops and year.")
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

    context = build_assistant_context(
        data=data,
        country=country,
        selected_items=selected_items,
        year_range=year_range,
        comparison_year=map_year,
        source_note=source_note,
    )
    with assistant_tab:
        st.subheader("Ask About This Dashboard")
        st.caption("Ask about the selected country, crops, map, rankings, or trends.")
        groq_model = get_secret_value("GROQ_MODEL", DEFAULT_GROQ_MODEL)
        groq_api_key = get_secret_value("GROQ_API_KEY")
        question = st.text_area(
            "Question",
            placeholder="Example: Which selected crop dominates South America in the selected end year?",
            height=96,
        )
        if st.button("Ask AI Assistant", type="primary"):
            if not question.strip():
                st.warning("Enter a question first.")
            elif not groq_api_key:
                st.warning("The AI assistant is not configured yet. Add GROQ_API_KEY in Streamlit secrets.")
            else:
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
