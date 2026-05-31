"""
Build the processed dataset that powers the dashboard.

Pipeline
--------
1. Download the FAOSTAT "Crops and livestock products" bulk file (if missing).
2. Stream the 545 MB CSV in chunks, keeping only:
      Element Code 5510 (Production) measured in tonnes, Value > 0.
3. Categorize each item (src/categories.py); drop aggregates / processed items.
4. Map FAO country names to ISO-3 codes (for Plotly choropleths) and drop
   regional aggregates ("World", "Africa", ...).
5. Write a compact long-format table to data/processed/production.parquet.

Run:  python prepare_data.py
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src import categories as C  # noqa: E402

ROOT = Path(__file__).resolve().parent
RAW_ZIP = ROOT / "data" / "raw" / "qcl.zip"
OUT_PARQUET = ROOT / "data" / "processed" / "production.parquet"
CSV_NAME = "Production_Crops_Livestock_E_All_Data_(Normalized).csv"
BULK_URL = (
    "https://bulks-faostat.fao.org/production/"
    "Production_Crops_Livestock_E_All_Data_(Normalized).zip"
)

PRODUCTION_ELEMENT = 5510  # "Production" in tonnes
CHUNK = 2_000_000

# FAO area names that are regional/economic aggregates or cause double counting.
# "China" is the FAO super-aggregate (mainland+Taiwan+HK+Macao); we keep the
# individual territories instead, so the aggregate is dropped here.
DROP_AREAS = {"China"}


def download_if_missing() -> None:
    if RAW_ZIP.exists():
        print(f"[1/5] Using cached bulk file: {RAW_ZIP}")
        return
    RAW_ZIP.parent.mkdir(parents=True, exist_ok=True)
    print(f"[1/5] Downloading FAOSTAT bulk data ->\n      {BULK_URL}")
    # urllib gets reset by the FAO server; curl works reliably here.
    import subprocess

    rc = subprocess.call(
        ["curl", "-fL", "--retry", "3", "-A", "Mozilla/5.0",
         "-o", str(RAW_ZIP), BULK_URL]
    )
    if rc != 0 or not RAW_ZIP.exists():
        raise SystemExit(
            "Download failed. Manually download the zip from\n  "
            + BULK_URL
            + f"\nand save it as {RAW_ZIP}"
        )


def load_and_filter() -> pd.DataFrame:
    print("[2/5] Streaming + filtering production rows (tonnes)...")
    cols = ["Area", "Item Code", "Item", "Element Code", "Year", "Unit", "Value"]
    kept = []
    with zipfile.ZipFile(RAW_ZIP) as z, z.open(CSV_NAME) as fh:
        reader = pd.read_csv(
            fh, usecols=cols, encoding="latin-1", chunksize=CHUNK,
            dtype={"Item Code": "Int64", "Element Code": "Int64",
                   "Year": "Int64"},
        )
        for i, chunk in enumerate(reader, 1):
            m = (
                (chunk["Element Code"] == PRODUCTION_ELEMENT)
                & (chunk["Unit"].str.strip().str.lower().isin({"t", "tonnes"}))
                & (chunk["Value"] > 0)
            )
            kept.append(chunk.loc[m, ["Area", "Item Code", "Item", "Year", "Value"]])
            print(f"      chunk {i}: {int(m.sum()):>8,} rows kept")
    df = pd.concat(kept, ignore_index=True)
    print(f"      total production rows: {len(df):,}")
    return df


def add_categories(df: pd.DataFrame) -> pd.DataFrame:
    print("[3/5] Categorizing items (dropping aggregates / processed)...")
    df["category"] = df["Item Code"].map(C.categorize)
    before = len(df)
    df = df.dropna(subset=["category"]).copy()
    df["group"] = df["category"].map(C.GROUP_OF)
    print(f"      kept {len(df):,} of {before:,} rows after category filter")
    return df


def add_iso3(df: pd.DataFrame) -> pd.DataFrame:
    print("[4/5] Mapping countries to ISO-3 codes...")
    import logging
    import re

    import country_converter as coco

    logging.getLogger("country_converter").setLevel(logging.ERROR)

    # Overrides for names coco matches ambiguously or not at all.
    OVERRIDES = {"China, Taiwan Province of": "TWN"}

    df = df[~df["Area"].isin(DROP_AREAS)].copy()
    areas = sorted(df["Area"].unique())
    cc = coco.CountryConverter()
    iso = cc.convert(names=areas, to="ISO3", not_found=None)

    iso3_re = re.compile(r"^[A-Z]{3}$")
    name2iso = {}
    for a, code in zip(areas, iso):
        if a in OVERRIDES:
            name2iso[a] = OVERRIDES[a]
        elif isinstance(code, str) and iso3_re.match(code):
            # A valid ISO3 string; coco returns the original name when unmatched
            # and a list for ambiguous matches -- both correctly rejected here.
            name2iso[a] = code
    dropped = [a for a in areas if a not in name2iso]
    if dropped:
        print(f"      dropped {len(dropped)} non-country areas, e.g. "
              f"{dropped[:6]}")
    df["iso3"] = df["Area"].map(name2iso)
    df = df.dropna(subset=["iso3"]).copy()

    # A historical entity and a current one can both map to the same ISO3 in a
    # given year (rare). Collapse to one row per iso3/year/item by summing.
    df = (
        df.groupby(["iso3", "Area", "Year", "Item Code", "Item", "category",
                    "group"], as_index=False, observed=True)["Value"].sum()
    )
    print(f"      {df['iso3'].nunique()} countries, "
          f"years {int(df['Year'].min())}-{int(df['Year'].max())}")
    return df


def main() -> None:
    download_if_missing()
    df = load_and_filter()
    df = add_categories(df)
    df = add_iso3(df)

    df = df.rename(columns={
        "Area": "country", "Year": "year", "Item": "item",
        "Item Code": "item_code", "Value": "value_tonnes",
    })
    df = df[["iso3", "country", "year", "item", "item_code", "category",
             "group", "value_tonnes"]]
    df["year"] = df["year"].astype(int)
    df = df.sort_values(["year", "iso3", "value_tonnes"],
                        ascending=[True, True, False]).reset_index(drop=True)

    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PARQUET, index=False)
    size_mb = OUT_PARQUET.stat().st_size / 1e6
    print(f"[5/5] Wrote {len(df):,} rows -> {OUT_PARQUET} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
