"""Master data: 15 cafés (3 brands × 5) and ~30 menu items.

Each café has a `cafe_type` that drives its demand pattern (office cafés
peak weekdays at lunch; tourist cafés peak weekends; transit-area cafés
peak at morning/evening commute; hipster cafés have a long flat
afternoon-into-evening curve).

Menu items are price-tagged in EUR (single-currency MVP — we'll layer
multi-currency on per-café in a later iteration).
"""

from typing import TypedDict


class CafeSeed(TypedDict):
    code: str
    name: str
    brand: str
    city: str
    country: str
    cafe_type: str
    opening_hour: int
    closing_hour: int
    baseline_hourly_traffic: float  # peak-hour expected transactions


class MenuItemSeed(TypedDict):
    code: str
    name: str
    brand: str
    category: str          # coffee_hot / coffee_iced / food / retail
    price_eur: float


CAFES: list[CafeSeed] = [
    # ----- Bean&Brew (Italy + UK)
    {"code": "BB-MIL-01", "name": "Bean&Brew Milano Centrale",   "brand": "Bean&Brew",    "city": "Milano",     "country": "IT", "cafe_type": "transit", "opening_hour": 6, "closing_hour": 22, "baseline_hourly_traffic": 28.0},
    {"code": "BB-ROM-01", "name": "Bean&Brew Roma Trastevere",   "brand": "Bean&Brew",    "city": "Roma",       "country": "IT", "cafe_type": "tourist", "opening_hour": 7, "closing_hour": 23, "baseline_hourly_traffic": 22.0},
    {"code": "BB-NAP-01", "name": "Bean&Brew Napoli Spaccanapoli", "brand": "Bean&Brew",  "city": "Napoli",     "country": "IT", "cafe_type": "tourist", "opening_hour": 7, "closing_hour": 22, "baseline_hourly_traffic": 18.0},
    {"code": "BB-FLR-01", "name": "Bean&Brew Firenze Duomo",     "brand": "Bean&Brew",    "city": "Firenze",    "country": "IT", "cafe_type": "tourist", "opening_hour": 7, "closing_hour": 22, "baseline_hourly_traffic": 20.0},
    {"code": "BB-LON-01", "name": "Bean&Brew London Soho",       "brand": "Bean&Brew",    "city": "London",     "country": "GB", "cafe_type": "transit", "opening_hour": 6, "closing_hour": 21, "baseline_hourly_traffic": 25.0},

    # ----- NordRoast (Scandinavia + NL + DE)
    {"code": "NR-STO-01", "name": "NordRoast Stockholm Söder",   "brand": "NordRoast",    "city": "Stockholm",  "country": "SE", "cafe_type": "hipster", "opening_hour": 8, "closing_hour": 20, "baseline_hourly_traffic": 14.0},
    {"code": "NR-OSL-01", "name": "NordRoast Oslo Grünerløkka",  "brand": "NordRoast",    "city": "Oslo",       "country": "NO", "cafe_type": "hipster", "opening_hour": 8, "closing_hour": 20, "baseline_hourly_traffic": 12.0},
    {"code": "NR-CPH-01", "name": "NordRoast Copenhagen Vesterbro", "brand": "NordRoast", "city": "Copenhagen", "country": "DK", "cafe_type": "hipster", "opening_hour": 8, "closing_hour": 20, "baseline_hourly_traffic": 13.0},
    {"code": "NR-AMS-01", "name": "NordRoast Amsterdam Jordaan", "brand": "NordRoast",    "city": "Amsterdam",  "country": "NL", "cafe_type": "hipster", "opening_hour": 8, "closing_hour": 21, "baseline_hourly_traffic": 16.0},
    {"code": "NR-BER-01", "name": "NordRoast Berlin Mitte",      "brand": "NordRoast",    "city": "Berlin",     "country": "DE", "cafe_type": "hipster", "opening_hour": 8, "closing_hour": 22, "baseline_hourly_traffic": 18.0},

    # ----- Café Polonia (PL/CZ/SK)
    {"code": "CP-WAW-01", "name": "Café Polonia Mokotów",        "brand": "Café Polonia", "city": "Warszawa",   "country": "PL", "cafe_type": "office",  "opening_hour": 7, "closing_hour": 19, "baseline_hourly_traffic": 30.0},
    {"code": "CP-WAW-02", "name": "Café Polonia Wola",           "brand": "Café Polonia", "city": "Warszawa",   "country": "PL", "cafe_type": "office",  "opening_hour": 7, "closing_hour": 19, "baseline_hourly_traffic": 26.0},
    {"code": "CP-KRK-01", "name": "Café Polonia Stare Miasto",   "brand": "Café Polonia", "city": "Kraków",     "country": "PL", "cafe_type": "tourist", "opening_hour": 8, "closing_hour": 22, "baseline_hourly_traffic": 22.0},
    {"code": "CP-PRG-01", "name": "Café Polonia Praha Nové Město", "brand": "Café Polonia", "city": "Praha",    "country": "CZ", "cafe_type": "tourist", "opening_hour": 8, "closing_hour": 22, "baseline_hourly_traffic": 19.0},
    {"code": "CP-BRT-01", "name": "Café Polonia Bratislava Staré Mesto", "brand": "Café Polonia", "city": "Bratislava", "country": "SK", "cafe_type": "tourist", "opening_hour": 8, "closing_hour": 21, "baseline_hourly_traffic": 14.0},
]


MENU_ITEMS: list[MenuItemSeed] = [
    # ===== Bean&Brew (Italian classics)
    {"code": "BB-ESP",   "name": "Espresso",                  "brand": "Bean&Brew", "category": "coffee_hot",  "price_eur": 1.50},
    {"code": "BB-MAC",   "name": "Macchiato",                 "brand": "Bean&Brew", "category": "coffee_hot",  "price_eur": 2.00},
    {"code": "BB-CAP",   "name": "Cappuccino",                "brand": "Bean&Brew", "category": "coffee_hot",  "price_eur": 2.50},
    {"code": "BB-LAT",   "name": "Caffè Latte",               "brand": "Bean&Brew", "category": "coffee_hot",  "price_eur": 3.00},
    {"code": "BB-AME",   "name": "Americano",                 "brand": "Bean&Brew", "category": "coffee_hot",  "price_eur": 2.50},
    {"code": "BB-DEC",   "name": "Espresso Decaf",            "brand": "Bean&Brew", "category": "coffee_hot",  "price_eur": 1.80},
    {"code": "BB-ICED",  "name": "Iced Caffè Latte",          "brand": "Bean&Brew", "category": "coffee_iced", "price_eur": 3.50},
    {"code": "BB-COR",   "name": "Cornetto",                  "brand": "Bean&Brew", "category": "food",        "price_eur": 2.00},
    {"code": "BB-PAN",   "name": "Panini Prosciutto",         "brand": "Bean&Brew", "category": "food",        "price_eur": 5.50},
    {"code": "BB-BAG",   "name": "Whole Bean Bag (250g)",     "brand": "Bean&Brew", "category": "retail",      "price_eur": 15.00},

    # ===== NordRoast (specialty + filter)
    {"code": "NR-V60",     "name": "Hand-brew V60",           "brand": "NordRoast", "category": "coffee_hot",  "price_eur": 4.50},
    {"code": "NR-AERO",    "name": "AeroPress",               "brand": "NordRoast", "category": "coffee_hot",  "price_eur": 4.00},
    {"code": "NR-BATCH",   "name": "Batch Brew",              "brand": "NordRoast", "category": "coffee_hot",  "price_eur": 3.50},
    {"code": "NR-CAP",     "name": "Cappuccino",              "brand": "NordRoast", "category": "coffee_hot",  "price_eur": 3.50},
    {"code": "NR-FLAT",    "name": "Flat White",              "brand": "NordRoast", "category": "coffee_hot",  "price_eur": 3.80},
    {"code": "NR-OAT",     "name": "Flat White (oat)",        "brand": "NordRoast", "category": "coffee_hot",  "price_eur": 4.10},
    {"code": "NR-CHEM",    "name": "Chemex (300ml)",          "brand": "NordRoast", "category": "coffee_hot",  "price_eur": 5.00},
    {"code": "NR-COLD",    "name": "Cold Brew",               "brand": "NordRoast", "category": "coffee_iced", "price_eur": 4.50},
    {"code": "NR-PASTRY",  "name": "Cinnamon Bun",            "brand": "NordRoast", "category": "food",        "price_eur": 3.50},
    {"code": "NR-BAG",     "name": "Whole Bean Bag (250g)",   "brand": "NordRoast", "category": "retail",      "price_eur": 18.00},

    # ===== Café Polonia (mass-market)
    {"code": "CP-ESP",   "name": "Espresso",                  "brand": "Café Polonia", "category": "coffee_hot",  "price_eur": 1.40},
    {"code": "CP-AME",   "name": "Americano",                 "brand": "Café Polonia", "category": "coffee_hot",  "price_eur": 1.90},
    {"code": "CP-CAP",   "name": "Cappuccino",                "brand": "Café Polonia", "category": "coffee_hot",  "price_eur": 2.50},
    {"code": "CP-LAT",   "name": "Latte",                     "brand": "Café Polonia", "category": "coffee_hot",  "price_eur": 2.80},
    {"code": "CP-FLW",   "name": "Flat White",                "brand": "Café Polonia", "category": "coffee_hot",  "price_eur": 3.00},
    {"code": "CP-MOC",   "name": "Mocca",                     "brand": "Café Polonia", "category": "coffee_hot",  "price_eur": 3.20},
    {"code": "CP-ICE",   "name": "Iced Coffee",               "brand": "Café Polonia", "category": "coffee_iced", "price_eur": 3.00},
    {"code": "CP-MUF",   "name": "Muffin",                    "brand": "Café Polonia", "category": "food",        "price_eur": 1.90},
    {"code": "CP-SAN",   "name": "Sandwich",                  "brand": "Café Polonia", "category": "food",        "price_eur": 4.20},
    {"code": "CP-BAG",   "name": "Whole Bean Bag (250g)",     "brand": "Café Polonia", "category": "retail",      "price_eur": 11.50},
]
