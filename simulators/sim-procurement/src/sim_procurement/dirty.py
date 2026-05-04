"""Pure-function decisions for injecting realistic data quality issues.

Every function takes an explicit `random.Random` so behaviour is deterministic
under a fixed seed (good for tests and for reproducible learning sessions).
No DB or Kafka dependencies here — that's why this file is unit-testable
without spinning up containers.
"""

import random
from typing import NamedTuple


# ----------------------------- Supplier name on invoice -----------------------------

def choose_invoice_name(
    canonical: str,
    variants: list[str],
    rng: random.Random,
    p_variant: float = 0.30,
) -> str:
    """30% of the time, the supplier's invoice carries a typo'd / case-different /
    legal-form-different version of their name instead of the canonical master-data one."""
    if not variants or rng.random() >= p_variant:
        return canonical
    return rng.choice(variants)


# ----------------------------- Invoice currency + FX -----------------------------

class InvoiceMoney(NamedTuple):
    invoice_currency: str
    invoice_amount: float
    fx_rate_recorded: float | None  # None when invoice_currency == contract currency
                                    # OR when operator forgot to record it


def choose_invoice_money(
    contract_amount: float,
    contract_currency: str,
    fx_rates: dict[tuple[str, str], float],
    rng: random.Random,
    p_invoice_in_eur: float = 0.20,
    fx_jitter: float = 0.02,
    p_missing_fx_rate: float = 0.05,
) -> InvoiceMoney:
    """Pick whether the supplier invoiced in their contract currency or in EUR
    (the buyer's currency), apply an FX rate with realistic jitter, and
    occasionally "forget" to record the rate."""
    if contract_currency == "EUR" or rng.random() >= p_invoice_in_eur:
        return InvoiceMoney(contract_currency, round(contract_amount, 2), None)

    # Different currency — apply FX with jitter
    base_rate = fx_rates.get((contract_currency, "EUR"))
    if base_rate is None:
        # Unknown FX pair: fall back to same-currency invoicing.
        return InvoiceMoney(contract_currency, round(contract_amount, 2), None)

    jitter = rng.uniform(1 - fx_jitter, 1 + fx_jitter)
    rate = round(base_rate * jitter, 4)
    invoice_amount = round(contract_amount * rate, 2)
    recorded_rate: float | None = None if rng.random() < p_missing_fx_rate else rate
    return InvoiceMoney("EUR", invoice_amount, recorded_rate)


# ----------------------------- Arrival outcome -----------------------------

class ArrivalDecision(NamedTuple):
    status: str            # on_time / delayed / very_delayed / lost
    delay_days: int        # negative = early; 0 if lost


def decide_arrival(rng: random.Random) -> ArrivalDecision:
    """Decide what happens with a shipment that's due to arrive.

    Buckets (cumulative): 60% on_time, +25% delayed, +10% very_delayed, +5% lost.
    """
    r = rng.random()
    if r < 0.60:
        return ArrivalDecision("on_time", rng.randint(-2, 2))
    if r < 0.85:
        return ArrivalDecision("delayed", rng.randint(5, 15))
    if r < 0.95:
        return ArrivalDecision("very_delayed", rng.randint(15, 45))
    return ArrivalDecision("lost", 0)


# ----------------------------- Quality outcome -----------------------------

class QualityDecision(NamedTuple):
    status: str                    # accepted / partial / rejected
    accepted_fraction: float       # 0.0 .. 1.0
    reason: str | None             # non-None for partial / rejected


def decide_quality(
    rng: random.Random,
    partial_reasons: list[str],
    rejected_reasons: list[str],
) -> QualityDecision:
    """For a shipment that physically arrived: did the lot pass QC?

    Buckets (cumulative): 90% accepted, +7% partial, +3% rejected.
    """
    r = rng.random()
    if r < 0.90:
        return QualityDecision("accepted", 1.0, None)
    if r < 0.97:
        frac = round(rng.uniform(0.5, 0.9), 3)
        return QualityDecision("partial", frac, rng.choice(partial_reasons))
    return QualityDecision("rejected", 0.0, rng.choice(rejected_reasons))
