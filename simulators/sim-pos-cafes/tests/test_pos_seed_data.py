from sim_pos_cafes.seed_data import CAFES, MENU_ITEMS


VALID_CATEGORIES = {"coffee_hot", "coffee_iced", "food", "retail"}
VALID_TYPES = {"office", "tourist", "hipster", "transit"}


def test_cafe_codes_unique():
    codes = [c["code"] for c in CAFES]
    assert len(codes) == len(set(codes))


def test_menu_codes_unique():
    codes = [m["code"] for m in MENU_ITEMS]
    assert len(codes) == len(set(codes))


def test_each_cafe_type_is_valid():
    bad = [c["code"] for c in CAFES if c["cafe_type"] not in VALID_TYPES]
    assert not bad


def test_opening_before_closing():
    bad = [c["code"] for c in CAFES if c["opening_hour"] >= c["closing_hour"]]
    assert not bad


def test_each_menu_category_is_valid():
    bad = [m["code"] for m in MENU_ITEMS if m["category"] not in VALID_CATEGORIES]
    assert not bad


def test_every_brand_has_full_category_coverage():
    """Every brand in our fleet must offer at least one item in coffee_hot
    and one in food. Without these, hourly category-mix sampling has no
    candidates to draw from at peak hours and we'd silently drop sales."""
    by_brand_cat = {(m["brand"], m["category"]) for m in MENU_ITEMS}
    brands = {c["brand"] for c in CAFES}
    required = {"coffee_hot", "food"}
    for brand in brands:
        for cat in required:
            assert (brand, cat) in by_brand_cat, f"{brand} missing {cat} on menu"


def test_every_brand_in_cafes_has_menu_items():
    cafe_brands = {c["brand"] for c in CAFES}
    menu_brands = {m["brand"] for m in MENU_ITEMS}
    assert cafe_brands.issubset(menu_brands)
