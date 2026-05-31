# 🌍 What the World Grows & Raises (1961–2024)

An interactive world-map dashboard showing, for every country and year, the
**top agricultural products** — colour-coded by category (crops, beef, poultry,
pork, sheep/goat, milk, eggs…). Built for the agentiki.ai Maven cohort
(Project 1).

Data: **UN FAO — FAOSTAT**, *Production: Crops and livestock products*
(production quantity, tonnes).

## What it does
- **World choropleth** with a year **slider + ▶ play button** to animate
  1961 → 2024.
- Two ways to read the map (switchable):
  - **Top product** — colour = the country's single #1 commodity.
  - **Dominant category** — colour = the category with the most combined
    tonnage among the country's top-N products.
- **Product filter** (All / Crops / Livestock & meat / **Meat only**) — because
  raw tonnage is dominated by crops, sugar cane and milk, this filter is what
  makes the *meat / dairy* story visible (use *Meat only* to surface
  beef / poultry / pork).
- **Specific-crop colouring:** under *Crops only* the map colours by the actual
  crop (rice / wheat / maize / sugar cane / cassava …) instead of a flat
  green "Crop", so you can read the rice belt, wheat belt, cassava belt, etc.
- **Hover** any country for its ranked top-N products.
- **Country drill-down**: top products for a chosen year + a stacked-area view
  of each category over time.

## 🎯 Getting the most out of the map
A few combinations that tell the best stories (great for a live walk-through):

| Want to show… | Set **Show which products** | Set **Colour by** | Then… |
|---|---|---|---|
| The classic "what does each country grow" | **Crops only** | Top product | Watch the rice / wheat / maize / cassava belts; press ▶ to see them shift 1961→2024 |
| Who the big **meat** producers are | **Meat only (no milk / eggs)** | Top product | China → pork, USA/Brazil → chicken, Australia/Argentina → beef |
| How **dairy** dominates livestock by weight | Livestock & meat | Dominant category | Most of the world turns "Milk" blue |
| A single country's full story | (any) | (any) | Use the **drill-down**: pick a country, scrub the year, read the "over time" area chart |

Tips:
- **Hover** a country to see its ranked top-N with exact tonnages.
- The **Top-N slider** changes how many products feed the hover list and the
  "dominant" calculation.
- Press **▶** (bottom-left of the map) to animate; drag the slider to jump to a year.
- Open **ℹ️ About the data & method** in the sidebar for the data caveats.

## Quick start
```
pip install -r requirements.txt
python main.py
```
`python main.py` builds the dataset on first run (downloads ~34 MB from
FAOSTAT), then launches the dashboard. To run the pieces separately:
```
python prepare_data.py          # build data/processed/production.parquet
streamlit run app.py            # launch the dashboard
```

## How the data is built (`prepare_data.py`)
1. Download the FAOSTAT bulk file (`data/raw/qcl.zip`, ~34 MB).
2. Stream the 545 MB CSV, keeping only **Production (element 5510) in tonnes**.
3. **Categorize** items (`src/categories.py`):
   - Drop FAO **aggregate** items ("Meat; Total", "Cereals; primary"…) so they
     don't dominate or double-count.
   - Drop **processed/derived** products (oils, refined sugar, wine, beer,
     cheese/butter/milk powder) so categories reflect *primary* production.
4. Map FAO country names → **ISO-3** codes (drops regional aggregates).
5. Save a compact long-format table to `data/processed/production.parquet`.

## 🚀 Run it online (so anyone can hover the map)
The repo ships the prebuilt `data/processed/production.parquet`, so the live app
needs **no download at runtime** — it just runs `app.py`.

**Streamlit Community Cloud (free, ~2 minutes):**
1. This project lives in the GitHub repo `ravikiran1993/agentic_ai_practise`
   under the `project1/` folder.
2. Go to **https://share.streamlit.io** and sign in with GitHub.
3. **Create app → From existing repo**, then choose:
   - Repository: `ravikiran1993/agentic_ai_practise`
   - Branch: `main`
   - **Main file path: `project1/app.py`**  ← note the `project1/` prefix
4. Click **Deploy**. You'll get a public URL like
   `https://<something>.streamlit.app` that anyone can open and
   hover/animate — no install required.

Streamlit Cloud reads `requirements.txt` automatically. Because the processed
parquet is committed, the app starts instantly and never needs the 545 MB
FAOSTAT download (that's only for rebuilding the data via `prepare_data.py`).

## Known limitations / honest caveats
- **Year range is 1961–2024.** FAOSTAT production starts in 1961, so the
  1950–1960 part of the original idea isn't available from this source.
- **Tonnage skew.** Crops/sugar cane/milk vastly outweigh meat by weight, so
  "top product" is almost always a crop — use the **Livestock & meat** filter.
- **Fish & seafood are not in this FAOSTAT domain.** They live in the FAO
  Fisheries & Aquaculture dataset (different units/items). Those two categories
  are defined in the code and reserved for a phase-2 integration.

## Structure
```
agentiki-project/
├── main.py             # entry point: builds data (if needed) + launches app
├── prepare_data.py     # FAOSTAT download + ETL -> parquet
├── app.py              # Streamlit + Plotly dashboard
├── src/
│   └── categories.py   # item-code -> category mapping + exclusions
├── data/
│   ├── raw/            # downloaded FAOSTAT zip (gitignored)
│   └── processed/      # production.parquet
├── requirements.txt
├── CLAUDE.md
└── README.md
```
