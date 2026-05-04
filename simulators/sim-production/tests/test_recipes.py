"""Sanity checks on the master-data seed for recipes — broken ratios or
references break startup loudly."""

from sim_procurement.seed_data import VARIETIES as PROCUREMENT_VARIETIES
from sim_production.seed_data import BLEND_RECIPES, ROASTED_SKUS


def test_sku_codes_unique():
    codes = [s["code"] for s in ROASTED_SKUS]
    assert len(codes) == len(set(codes))


def test_every_recipe_row_points_to_existing_sku():
    sku_codes = {s["code"] for s in ROASTED_SKUS}
    orphans = [r for r in BLEND_RECIPES if r["sku_code"] not in sku_codes]
    assert not orphans, f"recipes referencing missing SKUs: {orphans}"


def test_recipes_sum_to_one_per_sku():
    by_sku: dict[str, float] = {}
    for r in BLEND_RECIPES:
        by_sku[r["sku_code"]] = by_sku.get(r["sku_code"], 0.0) + r["percentage"]
    bad = {sku: s for sku, s in by_sku.items() if abs(s - 1.0) > 1e-6}
    assert not bad, f"recipes whose percentages don't sum to 1.0: {bad}"


def test_every_sku_has_a_recipe():
    sku_codes_with_recipes = {r["sku_code"] for r in BLEND_RECIPES}
    missing = [s["code"] for s in ROASTED_SKUS if s["code"] not in sku_codes_with_recipes]
    assert not missing, f"SKUs without recipes: {missing}"


def test_every_recipe_variety_exists_in_procurement_seed():
    """Recipes reference procurement variety codes opaquely — but if the
    seed data drifts, we want CI to scream rather than the simulator
    silently skipping batches at runtime."""
    procurement_codes = {v["code"] for v in PROCUREMENT_VARIETIES}
    missing = sorted({
        r["variety_code"] for r in BLEND_RECIPES
        if r["variety_code"] not in procurement_codes
    })
    assert not missing, (
        f"recipes reference variety codes not in procurement seed: {missing}"
    )
