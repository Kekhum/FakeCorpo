# %% [markdown]
# # 01 — Platform overview
#
# Connect to the three domain databases that live inside the running Postgres
# container and get a sense of scale, freshness, and (important) **how dirty
# the data is on purpose**.
#
# Run this with the stack up:
#
# ```
# make up
# fakecorpo clock speed 86400      # backfill quickly
# # wait ~30s
# ```
#
# All three databases share the same Postgres host (`localhost:5432`) and the
# same user (`fakecorpo`/`fakecorpo`). In a real org each domain would be on
# its own server — joining across them is your job, not the simulator's.

# %%
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")  # safe no-op in Jupyter; fixes Windows console
except Exception:
    pass

import pandas as pd
from sqlalchemy import create_engine

engines = {
    "procurement": create_engine("postgresql+psycopg2://fakecorpo:fakecorpo@localhost:5432/db_procurement"),
    "production":  create_engine("postgresql+psycopg2://fakecorpo:fakecorpo@localhost:5432/db_production"),
    "pos":         create_engine("postgresql+psycopg2://fakecorpo:fakecorpo@localhost:5432/db_pos"),
}

# %% [markdown]
# ## What's in each database

# %%
TABLE_QUERY = """
SELECT relname AS table_name, n_live_tup AS rows
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY rows DESC, relname
"""

for name, eng in engines.items():
    print(f"\n=== {name} ===")
    print(pd.read_sql(TABLE_QUERY, eng).to_string(index=False))

# %% [markdown]
# ## Headline numbers
#
# If any of these are zero or in the single digits, your simulator hasn't run
# long enough yet — bump the clock and try again.

# %%
def scalar(engine, sql):
    return pd.read_sql(sql, engine).iloc[0, 0]

def n(eng, sql):
    return scalar(eng, sql)

PROC = engines["procurement"]
PROD = engines["production"]
POSDB = engines["pos"]

settled_sql   = "SELECT COUNT(*) FROM purchase_orders WHERE arrival_status IS NOT NULL"
completed_sql = "SELECT COUNT(*) FROM roasting_batches WHERE status = 'completed'"

print(f"Suppliers:           {n(PROC, 'SELECT COUNT(*) FROM suppliers')}")
print(f"Coffee varieties:    {n(PROC, 'SELECT COUNT(*) FROM coffee_varieties')}")
print(f"Purchase orders:     {n(PROC, 'SELECT COUNT(*) FROM purchase_orders')}")
print(f"  ... settled:       {n(PROC, settled_sql)}")
print(f"Roasted SKUs:        {n(PROD, 'SELECT COUNT(*) FROM roasted_skus')}")
print(f"Batches:             {n(PROD, 'SELECT COUNT(*) FROM roasting_batches')}")
print(f"  ... completed:     {n(PROD, completed_sql)}")
print(f"Cafés:               {n(POSDB, 'SELECT COUNT(*) FROM cafes')}")
print(f"Menu items:          {n(POSDB, 'SELECT COUNT(*) FROM menu_items')}")
print(f"POS transactions:    {n(POSDB, 'SELECT COUNT(*) FROM transactions')}")

# %% [markdown]
# ## Dirty-data showcase #1 — supplier names on invoices
#
# The same supplier shows up under many spellings on their own invoices.
# Joining naively on text would create phantom duplicates. **This is the MDM
# problem in miniature** — and it's everywhere in real enterprise data.

# %%
mdm = pd.read_sql("""
    SELECT s.name AS canonical,
           po.supplier_name_on_invoice AS as_invoiced,
           COUNT(*) AS occurrences
    FROM purchase_orders po
    JOIN suppliers s ON s.id = po.supplier_id
    WHERE po.supplier_name_on_invoice IS NOT NULL
      AND po.supplier_name_on_invoice <> s.name
    GROUP BY canonical, as_invoiced
    ORDER BY canonical, occurrences DESC
""", engines["procurement"])
mdm.head(20)

# %% [markdown]
# ## Dirty-data showcase #2 — invoices billed in EUR while contract is USD
#
# 20% of invoices come in EUR (we're a Dutch holding) even though the contract
# was struck in USD. The recorded FX rate jitters around the market and 5% of
# the time is missing entirely.

# %%
fx = pd.read_sql("""
    SELECT po_number, currency AS contract_ccy, total_amount AS contract,
           invoice_currency AS invoice_ccy, invoice_amount AS invoice,
           fx_rate_recorded AS fx
    FROM purchase_orders
    WHERE invoice_currency = 'EUR' AND currency <> 'EUR'
    ORDER BY id DESC
    LIMIT 10
""", engines["procurement"])
fx

# %% [markdown]
# ## Dirty-data showcase #3 — arrival outcomes
#
# Real shipments don't all land on time and pristine. Roughly 60/25/10/5
# on_time/delayed/very_delayed/lost, and inside arrivals roughly 90/7/3
# accepted/partial/rejected.

# %%
arrivals = pd.read_sql("""
    SELECT arrival_status,
           COUNT(*) AS pos,
           ROUND(AVG((sim_actual_arrival::date - sim_expected_arrival::date))::numeric, 1) AS avg_delay_days
    FROM purchase_orders
    WHERE arrival_status IS NOT NULL
    GROUP BY arrival_status
    ORDER BY pos DESC
""", engines["procurement"])
arrivals

# %% [markdown]
# ## Production yield — weight loss + cupping outcomes

# %%
batches = pd.read_sql("""
    SELECT status,
           COUNT(*) AS n,
           ROUND(AVG(weight_loss_pct)::numeric * 100, 2) AS avg_loss_pct,
           ROUND(AVG(cupping_score)::numeric, 1) AS avg_cupping
    FROM roasting_batches
    WHERE status IN ('completed','rejected')
    GROUP BY status
""", engines["production"])
batches

# %% [markdown]
# ## POS — hour-of-day curve
#
# This is the kind of plot a BI dashboard would show. Lunch peak is the
# strongest signal in the data.

# %%
hourly = pd.read_sql("""
    SELECT EXTRACT(HOUR FROM sim_at)::int AS hour, COUNT(*) AS txns
    FROM transactions
    GROUP BY hour ORDER BY hour
""", engines["pos"])

try:
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(hourly["hour"], hourly["txns"])
    ax.set_xlabel("Hour of day (sim)")
    ax.set_ylabel("Transactions")
    ax.set_title("POS transactions by hour of day")
    plt.tight_layout()
    plt.show()
except ImportError:
    print(hourly.to_string(index=False))
