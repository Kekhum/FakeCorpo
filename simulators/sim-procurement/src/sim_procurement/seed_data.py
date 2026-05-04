"""Master data for the procurement domain.

Kept as plain Python lists so the seed step is reviewable in a diff.
Real-world data wouldn't live in code, but for a fictional company this
keeps the simulator self-contained and reproducible.
"""

from typing import TypedDict


class SupplierSeed(TypedDict):
    code: str
    name: str
    country: str
    currency: str
    payment_terms_days: int
    quality_rating: float


class VarietySeed(TypedDict):
    code: str
    name: str
    supplier_code: str
    origin_country: str
    region: str
    variety: str
    processing: str
    grade: str
    base_price_usd_per_kg: float


SUPPLIERS: list[SupplierSeed] = [
    {"code": "ETH-001", "name": "Yirgacheffe Coffee Cooperative",   "country": "ET", "currency": "USD", "payment_terms_days": 30, "quality_rating": 0.92},
    {"code": "ETH-002", "name": "Sidamo Specialty Coffee Ltd",      "country": "ET", "currency": "USD", "payment_terms_days": 30, "quality_rating": 0.88},
    {"code": "BRA-001", "name": "Fazenda Cerrado Mineiro",          "country": "BR", "currency": "USD", "payment_terms_days": 45, "quality_rating": 0.85},
    {"code": "BRA-002", "name": "Sul de Minas Cooperative",         "country": "BR", "currency": "USD", "payment_terms_days": 45, "quality_rating": 0.83},
    {"code": "COL-001", "name": "Huila Specialty Beans S.A.S.",     "country": "CO", "currency": "USD", "payment_terms_days": 30, "quality_rating": 0.90},
    {"code": "COL-002", "name": "Antioquia Coffee Exporters",       "country": "CO", "currency": "USD", "payment_terms_days": 30, "quality_rating": 0.87},
    {"code": "VNM-001", "name": "Buon Ma Thuot Robusta Co.",        "country": "VN", "currency": "USD", "payment_terms_days": 60, "quality_rating": 0.78},
    {"code": "IDN-001", "name": "Sumatra Mandheling Coop",          "country": "ID", "currency": "USD", "payment_terms_days": 45, "quality_rating": 0.84},
    {"code": "KEN-001", "name": "Kenyan Coffee Auction Direct",     "country": "KE", "currency": "USD", "payment_terms_days": 14, "quality_rating": 0.93},
    {"code": "GTM-001", "name": "Antigua Highland Coffee",          "country": "GT", "currency": "USD", "payment_terms_days": 30, "quality_rating": 0.89},
]


# Alternative spellings / case variants / legal-form variants that occasionally
# appear on supplier-issued invoices. Picking from these (instead of the
# canonical `name` field) is one of the dirty-data injection vectors.
SUPPLIER_NAME_VARIANTS: dict[str, list[str]] = {
    "ETH-001": ["Yirgacheffe Coffee Co-operative", "Yirgacheffe Coffee Cooperative.", "YIRGACHEFFE COFFEE COOPERATIVE", "Yirgacheffe Coffee Coop"],
    "ETH-002": ["Sidamo Specialty Coffee LTD", "Sidamo Speciality Coffee Ltd", "Sidamo Specialty Coffee Limited"],
    "BRA-001": ["Faz. Cerrado Mineiro", "Fazenda Cerrado Mineiro S.A.", "FAZENDA CERRADO MINEIRO"],
    "BRA-002": ["Sul de Minas Coop", "Cooperativa Sul de Minas", "Sul de Minas Cooperative."],
    "COL-001": ["Huila Specialty Beans S.A.S", "Huila Specialty Beans", "HUILA SPECIALTY BEANS S.A.S."],
    "COL-002": ["Antioquia Coffee Exp.", "Antioquia Coffee Exporters Ltda", "Antioquia Cofee Exporters"],
    "VNM-001": ["Buon Ma Thuot Robusta", "BMT Robusta Co.", "Buon Ma Thuot Robusta Company"],
    "IDN-001": ["Sumatra Mandheling Cooperative", "Mandheling Coop", "PT Sumatra Mandheling"],
    "KEN-001": ["Kenyan Coffee Auction", "Kenya Coffee Auction Direct", "KENYAN COFFEE AUCTION DIRECT"],
    "GTM-001": ["Antigua Highland Coffee S.A.", "Antigua Highland", "Antigua Highland Coffee Co."],
}


# Approximate FX rates (mid-market, no time variation in this iteration —
# just a static table the simulator multiplies with a small jitter).
# Keyed by (from_currency, to_currency).
FX_RATES: dict[tuple[str, str], float] = {
    ("USD", "EUR"): 0.92,
    ("EUR", "USD"): 1.09,
}


# Distinct rejection reasons by quality tier.
QUALITY_PARTIAL_REASONS: list[str] = [
    "moisture content above 12.5%",
    "defects above contract spec",
    "partial damage in transit",
    "underweight bags detected",
    "infestation in 3 bags",
]
QUALITY_REJECTED_REASONS: list[str] = [
    "fungus contamination across lot",
    "moisture out of spec (>14%)",
    "wrong variety shipped",
    "unacceptable defect count (Grade 3)",
    "container compromised — full lot loss",
]


VARIETIES: list[VarietySeed] = [
    {"code": "ETH-YIRG-W",  "name": "Ethiopia Yirgacheffe Washed",       "supplier_code": "ETH-001", "origin_country": "ET", "region": "Yirgacheffe",     "variety": "arabica", "processing": "washed",     "grade": "AA", "base_price_usd_per_kg": 7.50},
    {"code": "ETH-SID-N",   "name": "Ethiopia Sidamo Natural",           "supplier_code": "ETH-002", "origin_country": "ET", "region": "Sidamo",          "variety": "arabica", "processing": "natural",    "grade": "A",  "base_price_usd_per_kg": 6.80},
    {"code": "BRA-CER-N",   "name": "Brazil Cerrado Natural",            "supplier_code": "BRA-001", "origin_country": "BR", "region": "Cerrado Mineiro", "variety": "arabica", "processing": "natural",    "grade": "A",  "base_price_usd_per_kg": 5.20},
    {"code": "BRA-CER-H",   "name": "Brazil Cerrado Honey",              "supplier_code": "BRA-001", "origin_country": "BR", "region": "Cerrado Mineiro", "variety": "arabica", "processing": "honey",      "grade": "A",  "base_price_usd_per_kg": 5.60},
    {"code": "BRA-SUL-W",   "name": "Brazil Sul de Minas Washed",        "supplier_code": "BRA-002", "origin_country": "BR", "region": "Sul de Minas",    "variety": "arabica", "processing": "washed",     "grade": "A",  "base_price_usd_per_kg": 5.50},
    {"code": "COL-HUI-W",   "name": "Colombia Huila Washed",             "supplier_code": "COL-001", "origin_country": "CO", "region": "Huila",           "variety": "arabica", "processing": "washed",     "grade": "AA", "base_price_usd_per_kg": 6.50},
    {"code": "COL-HUI-N",   "name": "Colombia Huila Natural",            "supplier_code": "COL-001", "origin_country": "CO", "region": "Huila",           "variety": "arabica", "processing": "natural",    "grade": "A",  "base_price_usd_per_kg": 6.20},
    {"code": "COL-ANT-W",   "name": "Colombia Antioquia Washed",         "supplier_code": "COL-002", "origin_country": "CO", "region": "Antioquia",       "variety": "arabica", "processing": "washed",     "grade": "A",  "base_price_usd_per_kg": 6.00},
    {"code": "VNM-BMT-N",   "name": "Vietnam Buon Ma Thuot Robusta",     "supplier_code": "VNM-001", "origin_country": "VN", "region": "Buon Ma Thuot",   "variety": "robusta", "processing": "natural",    "grade": "B",  "base_price_usd_per_kg": 3.20},
    {"code": "IDN-SUM-WH",  "name": "Indonesia Sumatra Mandheling",      "supplier_code": "IDN-001", "origin_country": "ID", "region": "North Sumatra",   "variety": "arabica", "processing": "wet-hulled", "grade": "A",  "base_price_usd_per_kg": 5.80},
    {"code": "KEN-AA-W",    "name": "Kenya AA Washed",                   "supplier_code": "KEN-001", "origin_country": "KE", "region": "Nyeri",           "variety": "arabica", "processing": "washed",     "grade": "AA", "base_price_usd_per_kg": 7.80},
    {"code": "GTM-ANT-W",   "name": "Guatemala Antigua Washed",          "supplier_code": "GTM-001", "origin_country": "GT", "region": "Antigua",         "variety": "arabica", "processing": "washed",     "grade": "AA", "base_price_usd_per_kg": 6.40},
]
