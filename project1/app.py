"""
World food-production dashboard (Streamlit + Plotly).

Shows, for every country and year (FAOSTAT, 1961-2024), the top agricultural
products, coloured by category. Two ways to read the map:

  * "Top product"        -> colour = category of the country's #1 product
  * "Dominant category"  -> colour = category with the largest combined tonnage
                            among the country's top-N products

A category-group filter (All / Crops / Livestock & meat) lets you surface the
livestock story, which raw tonnage would otherwise bury under crops and milk.

Run:  streamlit run app.py     (or: python main.py)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

try:  # load GROQ_API_KEY etc. from a local .env if present
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

from src import categories as C
from src import assistant as A

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "processed" / "production.parquet"

st.set_page_config(page_title="World Food Production (1961-2024)",
                   page_icon="🌍", layout="wide")


# Product-filter options (a single source of truth, reused by the map and the
# drill-down so they always agree).
FILTER_ALL = "All products"
FILTER_CROPS = "Crops only"
FILTER_LIVESTOCK = "Livestock & meat (incl. milk, eggs)"
FILTER_MEAT = "Meat only (no milk / eggs)"
FILTER_OPTIONS = [FILTER_ALL, FILTER_CROPS, FILTER_LIVESTOCK, FILTER_MEAT]


@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    if not DATA.exists():
        return pd.DataFrame()
    return pd.read_parquet(DATA)


def filter_products(df: pd.DataFrame, choice: str) -> pd.DataFrame:
    """Apply the sidebar product filter to any production frame."""
    if choice == FILTER_CROPS:
        return df[df["group"] == C.GROUP_CROPS]
    if choice == FILTER_LIVESTOCK:
        return df[df["group"] == C.GROUP_LIVESTOCK]
    if choice == FILTER_MEAT:
        return df[df["category"].isin(C.MEAT_CATEGORIES)]
    return df  # FILTER_ALL


def color_field(df: pd.DataFrame, choice: str) -> pd.Series:
    """The dimension the map is coloured by.

    For the crops filter we colour by the *specific* crop (so the map isn't a
    sea of green); otherwise by the high-level category (Crop / Beef / ...).
    """
    if choice == FILTER_CROPS:
        return df["item_code"].map(C.CROP_LABELS).fillna(C.OTHER_CROP)
    return df["category"]


def color_spec(choice: str):
    """(colour map, legend order, legend title) for the current filter."""
    if choice == FILTER_CROPS:
        return C.CROP_COLORS, C.CROP_ORDER, "Top crop"
    return C.CATEGORY_COLORS, C.CATEGORY_ORDER, "Category"


@st.cache_data(show_spinner="Building map frames...")
def build_frames(choice: str, top_n: int, mode: str) -> pd.DataFrame:
    """One row per (year, country): the colour value + a hover summary."""
    df = filter_products(load_data(), choice)
    df = df.sort_values(["year", "iso3", "value_tonnes"],
                        ascending=[True, True, False])

    topn = df.groupby(["year", "iso3"], sort=False).head(top_n).copy()
    topn["rank"] = topn.groupby(["year", "iso3"], sort=False).cumcount() + 1
    topn["color"] = color_field(topn, choice)
    topn["line"] = (
        topn["rank"].astype(str) + ". " + topn["item"] + " — "
        + (topn["value_tonnes"] / 1e6).round(2).astype(str) + " Mt"
    )
    hover = (
        topn.groupby(["year", "iso3", "country"])["line"]
        .agg("<br>".join).reset_index().rename(columns={"line": "hover"})
    )

    if mode == "Top product":
        pick = topn.loc[topn["rank"] == 1, ["year", "iso3", "color"]]
    else:  # Dominant: the colour value with the most tonnage in the top-N
        agg = (topn.groupby(["year", "iso3", "color"], as_index=False)
               ["value_tonnes"].sum()
               .sort_values("value_tonnes", ascending=False))
        pick = agg.groupby(["year", "iso3"], as_index=False).first()[
            ["year", "iso3", "color"]]

    frames = pick.merge(hover, on=["year", "iso3"]).sort_values("year")
    return frames


def make_map(frames: pd.DataFrame, choice: str, mode: str) -> "px.Figure":
    cmap, order, legend_title = color_spec(choice)
    noun = "crop" if choice == FILTER_CROPS else "product/category"
    title = (f"Top {noun} per country" if mode == "Top product"
             else f"Dominant {legend_title.lower()} per country")
    fig = px.choropleth(
        frames,
        locations="iso3",
        color="color",
        hover_name="country",
        custom_data=["hover"],
        animation_frame="year",
        color_discrete_map=cmap,
        category_orders={"color": order},
        projection="natural earth",
        title=title,
    )
    fig.update_traces(
        hovertemplate="<b>%{hovertext}</b><br>%{customdata[0]}<extra></extra>"
    )
    fig.update_layout(
        height=620,
        margin=dict(l=0, r=0, t=40, b=0),
        legend_title_text=legend_title,
        geo=dict(showframe=False, showcoastlines=False),
    )
    # Make the animation a touch slower so it's readable in a live demo.
    if fig.layout.updatemenus:
        btn = fig.layout.updatemenus[0].buttons[0]
        btn.args[1]["frame"]["duration"] = 500
        btn.args[1]["transition"]["duration"] = 200
    return fig


def main() -> None:
    df = load_data()
    st.title("🌍 What the world grows & raises, 1961–2024")
    st.caption(
        "Top agricultural products by country and year — FAOSTAT production "
        "(tonnes). Colour = product category."
    )

    if df.empty:
        st.error(
            "No data found. Run **`python prepare_data.py`** first to download "
            "and build `data/processed/production.parquet`."
        )
        st.stop()

    # ---- Sidebar controls ----
    with st.sidebar:
        st.header("Controls")
        mode = st.radio(
            "Colour the map by",
            ["Top product", "Dominant category"],
            help="Top product: the country's single #1 commodity.\n\n"
                 "Dominant category: the category with the most combined "
                 "tonnage among the top-N commodities.",
        )
        group_choice = st.radio(
            "Show which products",
            FILTER_OPTIONS,
            help="Raw tonnage is dominated by crops, sugar cane and milk.\n\n"
                 "• **Livestock & meat** includes milk & eggs (milk usually "
                 "wins on weight).\n"
                 "• **Meat only** drops milk & eggs so beef / poultry / pork "
                 "actually surface.",
        )
        top_n = st.slider("Top-N per country (for hover & dominance)",
                          1, 10, 5)
        st.divider()
        with st.expander("ℹ️ About the data & method"):
            st.markdown(METHOD_NOTES)

    frames = build_frames(group_choice, top_n, mode)

    # ---- Map ----
    st.plotly_chart(make_map(frames, group_choice, mode),
                    use_container_width=True)
    st.caption(
        "Drag the slider or press ▶ to animate across years. Hover a country "
        "for its ranked top products. Source: FAOSTAT, UN FAO "
        "(Production: Crops and livestock products)."
    )

    # ---- Country drill-down ----
    st.subheader("🔎 Country drill-down")
    if group_choice != FILTER_ALL:
        st.caption(f"Filtered to **{group_choice}** (matches the map above).")
    countries = sorted(df["country"].unique())
    default = countries.index("India") if "India" in countries else 0
    col1, col2 = st.columns([1, 3])
    with col1:
        country = st.selectbox("Country", countries, index=default)
        year = st.slider("Year", int(df.year.min()), int(df.year.max()),
                         int(df.year.max()))
    # Honour the same product filter as the map so the two views agree.
    cdf = filter_products(df[df["country"] == country], group_choice).copy()
    cdf["color"] = color_field(cdf, group_choice)
    cmap, order, legend_title = color_spec(group_choice)

    with col2:
        ytop = (cdf[cdf["year"] == year].nlargest(top_n, "value_tonnes")
                .sort_values("value_tonnes"))
        if ytop.empty:
            st.info("No data for this country/year.")
        else:
            ytop = ytop.assign(Mt=ytop["value_tonnes"] / 1e6)
            bar = px.bar(
                ytop, x="Mt", y="item", color="color", orientation="h",
                color_discrete_map=cmap,
                category_orders={"color": order},
                title=f"{country} — top {top_n} products in {year} (million tonnes)",
            )
            bar.update_layout(height=380, margin=dict(l=0, r=0, t=40, b=0),
                              yaxis_title="", xaxis_title="Million tonnes",
                              legend_title_text=legend_title)
            st.plotly_chart(bar, use_container_width=True)

    # Mix over time for the selected country (by the same colour dimension).
    mix = (cdf.groupby(["year", "color"], as_index=False)["value_tonnes"]
           .sum())
    mix["Mt"] = mix["value_tonnes"] / 1e6
    area = px.area(
        mix, x="year", y="Mt", color="color",
        color_discrete_map=cmap,
        category_orders={"color": order},
        title=f"{country} — production by {legend_title.lower()} over time (million tonnes)",
    )
    area.update_layout(height=360, margin=dict(l=0, r=0, t=40, b=0),
                       xaxis_title="", yaxis_title="Million tonnes",
                       legend_title_text=legend_title)
    st.plotly_chart(area, use_container_width=True)

    # ---- AI data assistant (Groq) ----
    st.divider()
    render_assistant(df, country, year, top_n)


def render_assistant(df: pd.DataFrame, country: str, year: int,
                     top_n: int) -> None:
    st.subheader("🤖 Ask the data assistant (Groq)")
    if not A.get_api_key():
        st.info(
            "Add your **free Groq API key** to turn on the assistant "
            "(no credit card needed).\n\n"
            "- **Locally:** create a `.env` file with `GROQ_API_KEY=gsk_...` "
            "(see `.env.example`).\n"
            "- **On Streamlit Cloud:** *Manage app → Settings → Secrets* and add "
            "`GROQ_API_KEY = \"gsk_...\"`.\n\n"
            "Get a free key at https://console.groq.com — then reload."
        )
        return

    st.caption(
        f"Grounded in the data for **{country}, {year}** plus that year's global "
        "leaders. Ask things like *“Why is sugar cane India's top crop?”* or "
        "*“How has its production mix changed since 1961?”*"
    )
    context = A.build_context(df, country, year, top_n)

    if st.button(f"💡 Generate insights for {country}"):
        with st.spinner("Asking Groq…"):
            try:
                st.session_state["insight"] = A.generate_insights(context, country)
            except Exception as e:  # noqa: BLE001
                st.session_state["insight"] = f"⚠️ {e}"
    if st.session_state.get("insight"):
        st.markdown(st.session_state["insight"])

    st.session_state.setdefault("chat", [])
    for m in st.session_state["chat"]:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    with st.form("assistant_form", clear_on_submit=True):
        q = st.text_input(f"Ask about {country} or the data",
                          placeholder="Type a question…")
        submitted = st.form_submit_button("Ask")
    if submitted and q:
        st.session_state["chat"].append({"role": "user", "content": q})
        history = st.session_state["chat"][:-1][-6:]
        with st.spinner("Thinking…"):
            try:
                ans = A.answer_question(q, context, history)
            except Exception as e:  # noqa: BLE001
                ans = f"⚠️ Couldn't reach the assistant: {e}"
        st.session_state["chat"].append({"role": "assistant", "content": ans})
        st.rerun()


METHOD_NOTES = """
**Source:** UN FAO — FAOSTAT, *Production: Crops and livestock products*
(bulk download), production quantity in **tonnes**.

**Coverage:** 1961–2024, 200 countries. FAOSTAT production starts in **1961**,
so 1950–1960 is not available from this source.

**Categories** are derived from FAO item codes (see `src/categories.py`):
- FAO **aggregate** items ("Meat; Total", "Cereals; primary", …) are removed so
  they don't dominate or double-count.
- **Processed/derived** products (vegetable oils, refined sugar, wine, beer,
  cheese/butter/milk powder) are removed so categories reflect *primary*
  production.

**Why the product filter matters:** by raw tonnage, crops + sugar cane + milk
dwarf meat, so "top product" is almost always a crop, and within livestock milk
usually wins. Use *Livestock & meat* for the dairy+meat picture, or *Meat only
(no milk / eggs)* to see chicken / beef / pork on their own.

**Crops view colouring:** under *Crops only* the map colours by the **specific
crop** (rice / wheat / maize / sugar cane …) instead of a flat "Crop", so you
can read the rice belt, wheat belt, etc. Less common crops fall into
"Other crop".

**Fish & seafood** are **not** in this FAOSTAT domain — they live in the FAO
Fisheries & Aquaculture dataset (different units/items). Those categories are
defined in the code and reserved for a phase-2 integration.
"""

if __name__ == "__main__":
    main()
