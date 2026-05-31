"""
Commodity categorization for the FAOSTAT "Crops and livestock products" dataset.

The goal is to turn ~300 raw FAO item codes into a small, presentation-friendly
set of categories (Crop, Beef, Poultry, ...), while:

  * EXCLUDING FAO aggregate items ("Meat; Total", "Cereals; primary", ...) that
    would otherwise dominate every country's top-5 and double-count production.
  * EXCLUDING processed/derived products (vegetable oils, refined sugar, wine,
    beer, cheese/butter/milk powder) so a category reflects *primary* production
    and we don't count e.g. soybeans and soybean oil twice.

Everything that survives the exclusions and is not an explicitly listed animal
product is treated as a primary Crop.

Categories use FAO `Item Code` (the plain numeric code, not the CPC code).
"""

# Category display names (also the keys used for colouring in the app).
CROP = "Crop"
BEEF = "Beef & buffalo"
PORK = "Pork"
POULTRY = "Poultry (chicken etc.)"
SHEEP_GOAT = "Sheep & goat meat"
OTHER_MEAT = "Other meat"
MILK = "Milk (raw)"
EGGS = "Eggs"
OTHER_ANIMAL = "Other animal products"
FISH = "Fish"            # populated from the FAO Fisheries dataset (phase 2)
SEAFOOD = "Seafood"      # populated from the FAO Fisheries dataset (phase 2)

# High-level grouping used by the sidebar "category group" filter.
GROUP_CROPS = "Crops"
GROUP_LIVESTOCK = "Livestock & meat"

# The "flesh" meat categories -- i.e. livestock minus milk, eggs and the
# misc. non-meat animal products. Used by the "Meat only" filter so the
# actual meat story (beef / poultry / pork / ...) isn't buried under milk.
MEAT_CATEGORIES = {
    BEEF, PORK, POULTRY, SHEEP_GOAT, OTHER_MEAT, FISH, SEAFOOD,
}
GROUP_OF = {
    CROP: GROUP_CROPS,
    BEEF: GROUP_LIVESTOCK,
    PORK: GROUP_LIVESTOCK,
    POULTRY: GROUP_LIVESTOCK,
    SHEEP_GOAT: GROUP_LIVESTOCK,
    OTHER_MEAT: GROUP_LIVESTOCK,
    MILK: GROUP_LIVESTOCK,
    EGGS: GROUP_LIVESTOCK,
    OTHER_ANIMAL: GROUP_LIVESTOCK,
    FISH: GROUP_LIVESTOCK,
    SEAFOOD: GROUP_LIVESTOCK,
}

# A stable colour per category (used by Plotly's discrete colour map).
CATEGORY_COLORS = {
    CROP: "#4C9F38",          # green
    BEEF: "#A0522D",          # sienna
    PORK: "#E78AC3",          # pink
    POULTRY: "#FFB000",       # amber
    SHEEP_GOAT: "#8DA0CB",    # muted blue
    OTHER_MEAT: "#B15928",    # brown
    MILK: "#7FC7FF",          # light blue
    EGGS: "#F4E04D",          # yellow
    OTHER_ANIMAL: "#999999",  # grey
    FISH: "#1F78B4",          # blue
    SEAFOOD: "#6A3D9A",       # purple
}

# Ordered list, used for consistent legend ordering.
CATEGORY_ORDER = [
    CROP, BEEF, POULTRY, PORK, SHEEP_GOAT, MILK, EGGS,
    OTHER_MEAT, OTHER_ANIMAL, FISH, SEAFOOD,
]

# --- Specific-crop colouring (for the "Crops only" map) --------------------
# The flat "Crop" category makes the crops map all-green, so when the user
# filters to crops we colour by the *specific* commodity instead. Only crops
# that are actually a country's #1 somewhere get their own colour (keyed by FAO
# item code, which is stable); everything else falls into "Other crop".
OTHER_CROP = "Other crop"
# Kept short and human-readable: the globally significant staples plus the few
# regionally dominant crops, with a handful of intuitive merges (sugar
# cane+beet, sorghum+millet, bananas+plantains). ~13 named + "Other crop".
# Several item codes can map to the same label.
CROP_LABELS = {
    27: "Rice",
    15: "Wheat",
    56: "Maize",
    44: "Barley",
    83: "Sorghum & millet",
    79: "Sorghum & millet",
    116: "Potatoes",
    125: "Cassava",
    156: "Sugar crops",
    157: "Sugar crops",
    236: "Soybeans",
    254: "Oil palm",
    249: "Coconut",
    486: "Bananas & plantains",
    489: "Bananas & plantains",
    577: "Dates",
}
CROP_ORDER = [
    "Rice", "Wheat", "Maize", "Barley", "Sorghum & millet",
    "Potatoes", "Cassava", "Sugar crops",
    "Soybeans", "Oil palm", "Coconut", "Bananas & plantains", "Dates",
    OTHER_CROP,
]
# High-contrast qualitative palette (readability beats colour-semantics for a
# ~13-way choropleth). The high-coverage crops get the most distinct hues.
CROP_COLORS = {
    "Rice": "#1F77B4",                 # strong blue
    "Wheat": "#FF7F0E",                # orange
    "Maize": "#FFD92F",                # yellow
    "Barley": "#BCBD22",               # olive
    "Sorghum & millet": "#D62728",     # red
    "Potatoes": "#9467BD",             # purple
    "Cassava": "#8C564B",              # brown
    "Sugar crops": "#2CA02C",          # green
    "Soybeans": "#AEC7E8",             # pale blue
    "Oil palm": "#E377C2",             # magenta-pink
    "Coconut": "#17BECF",              # cyan
    "Bananas & plantains": "#FF9896",  # salmon
    "Dates": "#BC8F8F",                # rosy brown
    OTHER_CROP: "#CCCCCC",             # grey
}

# --- FAO aggregate / "total" items: always dropped -------------------------
AGGREGATE_CODES = {
    1714, 1717, 1720, 1723, 1726, 1729, 1730, 1732, 1735, 1738, 1745,
    1746, 1749, 1753, 17530, 1756, 1765, 1777, 1780, 1783, 1804, 1806,
    1807, 1808, 1809, 1811, 1816, 1841, 2029,
}

# --- Processed / derived products: dropped to keep "primary" view ----------
PROCESSED_CODES = {
    # vegetable oils
    60, 237, 244, 252, 257, 258, 261, 268, 271, 281, 290, 331, 334,
    # sugar & derivatives
    162, 165,
    # beverages
    51, 564,
    # processed tea, ginned cotton lint, margarine, tallow
    675, 767, 1242, 1225,
    # processed dairy (cream, butter, cheese, ghee, whey, yoghurt, milk powders)
    885, 886, 887, 888, 889, 890, 891, 894, 895, 896, 897, 898, 899, 900,
    901, 904, 952, 953, 955, 983, 984, 1021, 1022,
}

# --- Explicit animal-product mappings --------------------------------------
BEEF_CODES = {867, 947}                       # cattle + buffalo meat
PORK_CODES = {1035}
POULTRY_CODES = {1058, 1069, 1073, 1080, 1089}  # chicken, duck, goose, turkey, other birds
SHEEP_GOAT_CODES = {977, 1017}
OTHER_MEAT_CODES = {1097, 1108, 1111, 1127, 1141, 1151, 1158, 1163, 1166, 1176}
MILK_CODES = {882, 951, 982, 1020, 1130}      # raw milk: cattle, buffalo, sheep, goat, camel
EGGS_CODES = {1062, 1091}                      # hen eggs + other bird eggs
OTHER_ANIMAL_CODES = {                          # offal, fats, hides, wool, honey, silk, beeswax
    868, 948, 1018, 1036, 1037, 1043, 869, 949, 979, 1019, 1098, 1128, 1129,
    919, 957, 995, 1025, 987, 1182, 1183, 1185, 1186,
}

_ANIMAL_MAP = {}
for _codes, _cat in (
    (BEEF_CODES, BEEF),
    (PORK_CODES, PORK),
    (POULTRY_CODES, POULTRY),
    (SHEEP_GOAT_CODES, SHEEP_GOAT),
    (OTHER_MEAT_CODES, OTHER_MEAT),
    (MILK_CODES, MILK),
    (EGGS_CODES, EGGS),
    (OTHER_ANIMAL_CODES, OTHER_ANIMAL),
):
    for _c in _codes:
        _ANIMAL_MAP[_c] = _cat

# Codes that should be removed from the dataset entirely.
DROP_CODES = AGGREGATE_CODES | PROCESSED_CODES


def categorize(item_code) -> str | None:
    """Return the category for a FAO numeric item code.

    Returns ``None`` for items that should be dropped (aggregates / processed),
    so callers can filter them out.
    """
    try:
        code = int(item_code)
    except (TypeError, ValueError):
        return None  # non-numeric group codes (QA/QC/QD/QL/QP) -> drop
    if code in DROP_CODES:
        return None
    if code in _ANIMAL_MAP:
        return _ANIMAL_MAP[code]
    return CROP
