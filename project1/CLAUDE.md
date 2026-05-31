# Project context for Claude Code

This is **Project 1** for the agentiki.ai Maven cohort — a Python project built by vibe-coding.

## Conventions
- Python 3, standard library first; add dependencies to `requirements.txt`.
- Keep entry point in `main.py`.
- Put secrets in `.env` (never commit them).

## How to run
```
python main.py
```

## Notes
**Goal:** an interactive world-map dashboard (Streamlit + Plotly) showing, per
country and year, the top agricultural products colour-coded by category
(crops, beef, poultry, pork, sheep/goat, milk, eggs; fish/seafood reserved for
a phase-2 fisheries integration). A year slider/▶ animation drives the map.

**Data:** UN FAO FAOSTAT "Production: Crops and livestock products" (tonnes),
1961–2024. `prepare_data.py` downloads + ETLs it into
`data/processed/production.parquet`; `src/categories.py` holds the
item-code→category map and the aggregate/processed exclusion lists; `app.py` is
the dashboard.

**Run:** `python main.py` (builds data on first run, then launches Streamlit),
or `streamlit run app.py` directly.

**Gotchas:** FAOSTAT bulk download must use `curl` (urllib gets connection-reset
by the FAO server). Raw tonnage is crop/milk-dominated, so the app has a
Crops / Livestock-&-meat group filter to surface the meat story.
