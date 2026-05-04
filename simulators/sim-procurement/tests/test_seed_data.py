"""Sanity checks on the master-data seed — wrong references break startup."""

from sim_procurement.seed_data import SUPPLIERS, VARIETIES


def test_supplier_codes_unique():
    codes = [s["code"] for s in SUPPLIERS]
    assert len(codes) == len(set(codes)), "duplicate supplier codes in seed"


def test_variety_codes_unique():
    codes = [v["code"] for v in VARIETIES]
    assert len(codes) == len(set(codes)), "duplicate variety codes in seed"


def test_each_variety_points_to_existing_supplier():
    supplier_codes = {s["code"] for s in SUPPLIERS}
    orphans = [v["code"] for v in VARIETIES if v["supplier_code"] not in supplier_codes]
    assert not orphans, f"varieties referencing missing suppliers: {orphans}"


def test_variety_country_matches_its_supplier():
    by_code = {s["code"]: s for s in SUPPLIERS}
    mismatches = [
        v["code"] for v in VARIETIES
        if v["origin_country"] != by_code[v["supplier_code"]]["country"]
    ]
    assert not mismatches, f"origin_country != supplier.country: {mismatches}"
