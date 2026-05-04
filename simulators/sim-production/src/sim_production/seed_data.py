"""Master data: roasted SKUs and their blend recipes.

Each SKU's recipe MUST sum to exactly 1.0 across its rows (verified in tests).
`variety_code` references procurement's `coffee_varieties.code` — they're
opaque strings here (no FK), so a mismatch only blows up at roast time
when inventory lookup fails for the missing variety code.
"""

from typing import TypedDict


class SkuSeed(TypedDict):
    code: str
    name: str
    brand: str


class RecipeSeed(TypedDict):
    sku_code: str
    variety_code: str
    percentage: float


ROASTED_SKUS: list[SkuSeed] = [
    {"code": "BB-ESP-CLAS",  "name": "Bean&Brew Espresso Classico",         "brand": "Bean&Brew"},
    {"code": "BB-SO-ANT",    "name": "Bean&Brew Single Origin Antigua",     "brand": "Bean&Brew"},
    {"code": "NR-SO-YIRG",   "name": "NordRoast Single Origin Yirgacheffe", "brand": "NordRoast"},
    {"code": "NR-LIGHT",     "name": "NordRoast Light Blend",               "brand": "NordRoast"},
    {"code": "NR-HOUSE",     "name": "NordRoast House Blend",               "brand": "NordRoast"},
    {"code": "CP-OFFICE",    "name": "Café Polonia Office Blend",           "brand": "Café Polonia"},
    {"code": "CP-CREMA",     "name": "Café Polonia Crema",                  "brand": "Café Polonia"},
    {"code": "CP-MOCCA",     "name": "Café Polonia Mocca",                  "brand": "Café Polonia"},
]


BLEND_RECIPES: list[RecipeSeed] = [
    # BB-ESP-CLAS — flagship espresso, BR-heavy with COL/ETH for brightness
    {"sku_code": "BB-ESP-CLAS", "variety_code": "BRA-CER-N",  "percentage": 0.60},
    {"sku_code": "BB-ESP-CLAS", "variety_code": "COL-HUI-W",  "percentage": 0.30},
    {"sku_code": "BB-ESP-CLAS", "variety_code": "ETH-SID-N",  "percentage": 0.10},

    # BB-SO-ANT — single origin Guatemala
    {"sku_code": "BB-SO-ANT",   "variety_code": "GTM-ANT-W",  "percentage": 1.00},

    # NR-SO-YIRG — single origin Yirgacheffe (NordRoast's hero)
    {"sku_code": "NR-SO-YIRG",  "variety_code": "ETH-YIRG-W", "percentage": 1.00},

    # NR-LIGHT — bright, ETH+KEN
    {"sku_code": "NR-LIGHT",    "variety_code": "ETH-YIRG-W", "percentage": 0.70},
    {"sku_code": "NR-LIGHT",    "variety_code": "KEN-AA-W",   "percentage": 0.30},

    # NR-HOUSE — daily blend
    {"sku_code": "NR-HOUSE",    "variety_code": "COL-HUI-N",  "percentage": 0.50},
    {"sku_code": "NR-HOUSE",    "variety_code": "ETH-SID-N",  "percentage": 0.30},
    {"sku_code": "NR-HOUSE",    "variety_code": "GTM-ANT-W",  "percentage": 0.20},

    # CP-OFFICE — mass-market workhorse, robusta-fronted
    {"sku_code": "CP-OFFICE",   "variety_code": "VNM-BMT-N",  "percentage": 0.50},
    {"sku_code": "CP-OFFICE",   "variety_code": "BRA-CER-N",  "percentage": 0.30},
    {"sku_code": "CP-OFFICE",   "variety_code": "IDN-SUM-WH", "percentage": 0.20},

    # CP-CREMA — body & crema for milk drinks
    {"sku_code": "CP-CREMA",    "variety_code": "BRA-CER-H",  "percentage": 0.60},
    {"sku_code": "CP-CREMA",    "variety_code": "COL-ANT-W",  "percentage": 0.40},

    # CP-MOCCA — chocolatey filter blend
    {"sku_code": "CP-MOCCA",    "variety_code": "ETH-SID-N",  "percentage": 0.40},
    {"sku_code": "CP-MOCCA",    "variety_code": "BRA-SUL-W",  "percentage": 0.40},
    {"sku_code": "CP-MOCCA",    "variety_code": "COL-HUI-N",  "percentage": 0.20},
]


REJECTION_REASONS: list[str] = [
    "cupping score below QC threshold",
    "scorched on roast — burnt notes",
    "underdeveloped — grassy / vegetal",
    "uneven roast — defects above limit",
    "moisture re-absorption during cooling",
]
