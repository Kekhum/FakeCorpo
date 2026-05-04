"""Tests for the dirty-data injection layer.

These functions are deterministic given a seeded random.Random, so we can
verify both the *what* (correct currency / amount / status) and the *how
often* (rough distributional shape) without spinning up Postgres or Kafka.
"""

import random
from collections import Counter

import pytest

from sim_procurement.dirty import (
    choose_invoice_money,
    choose_invoice_name,
    decide_arrival,
    decide_quality,
)


# ----------------------------- choose_invoice_name -----------------------------

def test_invoice_name_returns_canonical_when_no_variants():
    rng = random.Random(0)
    assert choose_invoice_name("Canonical Co.", [], rng, p_variant=1.0) == "Canonical Co."


def test_invoice_name_uses_variants_at_configured_rate():
    rng = random.Random(42)
    canonical = "Canonical Co."
    variants = ["Canon. Co.", "CANONICAL CO."]
    n = 5000
    chosen = [
        choose_invoice_name(canonical, variants, rng, p_variant=0.30)
        for _ in range(n)
    ]
    variant_count = sum(1 for c in chosen if c != canonical)
    # Allow generous slack — distribution test, not exact count.
    assert 0.25 * n < variant_count < 0.35 * n


# ----------------------------- choose_invoice_money -----------------------------

FX = {("USD", "EUR"): 0.92}


def test_invoice_money_keeps_contract_ccy_when_p_zero():
    rng = random.Random(0)
    money = choose_invoice_money(
        contract_amount=10_000.0,
        contract_currency="USD",
        fx_rates=FX,
        rng=rng,
        p_invoice_in_eur=0.0,
    )
    assert money.invoice_currency == "USD"
    assert money.invoice_amount == 10_000.0
    assert money.fx_rate_recorded is None


def test_invoice_money_converts_to_eur_with_jitter_when_p_one():
    rng = random.Random(0)
    money = choose_invoice_money(
        contract_amount=10_000.0,
        contract_currency="USD",
        fx_rates=FX,
        rng=rng,
        p_invoice_in_eur=1.0,
        fx_jitter=0.02,
        p_missing_fx_rate=0.0,
    )
    assert money.invoice_currency == "EUR"
    # Within ±2% of 9200
    assert 9200 * 0.98 <= money.invoice_amount <= 9200 * 1.02
    assert money.fx_rate_recorded is not None


def test_invoice_money_can_drop_fx_rate():
    rng = random.Random(7)
    samples = [
        choose_invoice_money(
            10_000.0, "USD", FX, rng,
            p_invoice_in_eur=1.0,
            fx_jitter=0.0,
            p_missing_fx_rate=1.0,
        )
        for _ in range(50)
    ]
    assert all(s.fx_rate_recorded is None for s in samples)


def test_invoice_money_eur_contract_stays_eur():
    rng = random.Random(0)
    money = choose_invoice_money(
        contract_amount=5_000.0,
        contract_currency="EUR",
        fx_rates=FX,
        rng=rng,
        p_invoice_in_eur=1.0,  # force conversion attempt
    )
    assert money.invoice_currency == "EUR"
    assert money.invoice_amount == 5_000.0
    assert money.fx_rate_recorded is None


def test_invoice_money_unknown_pair_falls_back_to_contract_ccy():
    rng = random.Random(0)
    money = choose_invoice_money(
        contract_amount=1_000.0,
        contract_currency="JPY",  # not in FX table
        fx_rates=FX,
        rng=rng,
        p_invoice_in_eur=1.0,
    )
    assert money.invoice_currency == "JPY"
    assert money.fx_rate_recorded is None


# ----------------------------- decide_arrival -----------------------------

def test_decide_arrival_distribution_is_in_expected_buckets():
    rng = random.Random(2026)
    n = 20_000
    counts = Counter(decide_arrival(rng).status for _ in range(n))
    # Expected: 60 / 25 / 10 / 5
    assert 0.55 * n < counts["on_time"] < 0.65 * n
    assert 0.22 * n < counts["delayed"] < 0.28 * n
    assert 0.07 * n < counts["very_delayed"] < 0.13 * n
    assert 0.03 * n < counts["lost"] < 0.07 * n


def test_decide_arrival_lost_has_zero_delay():
    rng = random.Random(0)
    # Find a 'lost' outcome and verify delay_days == 0
    saw_lost = False
    for _ in range(5000):
        d = decide_arrival(rng)
        if d.status == "lost":
            assert d.delay_days == 0
            saw_lost = True
            break
    assert saw_lost, "lost outcomes should appear within 5k draws"


# ----------------------------- decide_quality -----------------------------

PARTIAL = ["moisture", "defects"]
REJECTED = ["fungus", "wrong variety"]


def test_decide_quality_distribution_is_in_expected_buckets():
    rng = random.Random(2026)
    n = 20_000
    counts = Counter(decide_quality(rng, PARTIAL, REJECTED).status for _ in range(n))
    # Expected: 90 / 7 / 3
    assert 0.86 * n < counts["accepted"] < 0.94 * n
    assert 0.05 * n < counts["partial"] < 0.10 * n
    assert 0.015 * n < counts["rejected"] < 0.05 * n


def test_decide_quality_accepted_fraction_invariant():
    rng = random.Random(0)
    for _ in range(2000):
        q = decide_quality(rng, PARTIAL, REJECTED)
        if q.status == "accepted":
            assert q.accepted_fraction == 1.0 and q.reason is None
        elif q.status == "rejected":
            assert q.accepted_fraction == 0.0 and q.reason in REJECTED
        else:
            assert 0.5 <= q.accepted_fraction <= 0.9 and q.reason in PARTIAL
