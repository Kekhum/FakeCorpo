# %% [markdown]
# # 02 — Cross-domain supply chain join
#
# **Goal**: trace every euro of café revenue back to the supplier country
# whose green coffee fed the roasting batches that filled the SKUs that were
# sold over the counter.
#
# This is the join that doesn't exist in any single database — exactly the
# situation a data engineer faces every day. We do it in pandas here for
# learning value; in a real warehouse you'd put each domain into its own
# schema and join in SQL (or have dbt build a `fact_revenue_with_origin`
# model on top).
#
# ## The three hops we have to make
#
# ```
# pos.transaction_lines.menu_item
#       ↓ (best-effort: by brand + a heuristic that maps menu coffee → roasted SKU)
# production.roasting_batches.sku_id
#       ↓ (each batch has batch_inputs telling us how many kg of which variety it consumed)
# procurement.purchase_orders.lines.variety_code (origin_country lives on coffee_varieties)
# ```
#
# Note: there's no direct FK across these — they share `variety_code` and `brand`
# as opaque strings. Welcome to integration.

# %%
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")  # safe no-op in Jupyter; fixes Windows console
except Exception:
    pass

import pandas as pd
from sqlalchemy import create_engine

procurement = create_engine("postgresql+psycopg2://fakecorpo:fakecorpo@localhost:5432/db_procurement")
production  = create_engine("postgresql+psycopg2://fakecorpo:fakecorpo@localhost:5432/db_production")
pos         = create_engine("postgresql+psycopg2://fakecorpo:fakecorpo@localhost:5432/db_pos")

# %% [markdown]
# ## Step 1 — origin map: variety_code → origin country
#
# Lives in procurement only.

# %%
variety_to_origin = pd.read_sql("""
    SELECT code AS variety_code, origin_country, region, base_price_usd_per_kg
    FROM coffee_varieties
""", procurement)
print(variety_to_origin)

# %% [markdown]
# ## Step 2 — production: which varieties fed which roasted SKU's batches
#
# `batch_inputs` is the lineage trail. Aggregate per SKU.

# %%
sku_input_mix = pd.read_sql("""
    SELECT s.code AS sku_code, s.brand, s.name AS sku_name,
           bi.variety_code, SUM(bi.quantity_kg) AS variety_kg
    FROM roasting_batches b
    JOIN roasted_skus s ON s.id = b.sku_id
    JOIN batch_inputs bi ON bi.batch_id = b.id
    WHERE b.status = 'completed'
    GROUP BY s.code, s.brand, s.name, bi.variety_code
""", production)
print(sku_input_mix.head(15))

# %% [markdown]
# Convert this to "share of each variety in each SKU's history":

# %%
totals = sku_input_mix.groupby("sku_code")["variety_kg"].transform("sum")
sku_input_mix["share"] = sku_input_mix["variety_kg"] / totals
sku_input_mix.head(10)

# %% [markdown]
# ## Step 3 — POS revenue per (brand, menu_item)
#
# The menu_items table doesn't (yet) have an explicit FK to a roasted SKU —
# we'll do a heuristic match by brand + a fuzzy keyword on coffee items.

# %%
revenue_per_menu = pd.read_sql("""
    SELECT m.brand, m.code AS menu_code, m.name AS menu_name, m.category,
           SUM(tl.quantity)        AS units,
           SUM(tl.line_total_eur)  AS rev_eur
    FROM transaction_lines tl
    JOIN menu_items m ON m.id = tl.menu_item_id
    GROUP BY m.brand, m.code, m.name, m.category
    ORDER BY rev_eur DESC
""", pos)
print(revenue_per_menu.head(10))

# %% [markdown]
# ## Step 4 — naïve coffee-only attribution
#
# For the slice of revenue that's coffee drinks, attribute it across each
# brand's roasted SKU mix proportionally. This is intentionally crude — DE/DS
# would refine with a proper menu→SKU mapping table; the simulator deliberately
# doesn't ship one so the integration stays a teaching moment.

# %%
coffee_rev = revenue_per_menu[revenue_per_menu["category"].isin(["coffee_hot", "coffee_iced"])].copy()
brand_rev = coffee_rev.groupby("brand", as_index=False)["rev_eur"].sum().rename(columns={"rev_eur": "brand_rev_eur"})

# Each brand's revenue is split across its SKUs in proportion to the SKU's
# total roasted output (a simple, honest assumption).
sku_output = pd.read_sql("""
    SELECT s.code AS sku_code, s.brand,
           SUM(b.output_kg) AS sku_kg
    FROM roasting_batches b JOIN roasted_skus s ON s.id = b.sku_id
    WHERE b.status = 'completed' AND b.output_kg IS NOT NULL
    GROUP BY s.code, s.brand
""", production)
brand_total_kg = sku_output.groupby("brand", as_index=False)["sku_kg"].sum().rename(columns={"sku_kg": "brand_total_kg"})
sku_output = sku_output.merge(brand_total_kg, on="brand")
sku_output["sku_share_of_brand"] = sku_output["sku_kg"] / sku_output["brand_total_kg"]

sku_rev = sku_output.merge(brand_rev, on="brand")
sku_rev["sku_attributed_eur"] = sku_rev["brand_rev_eur"] * sku_rev["sku_share_of_brand"]

# Now spread each SKU's attributed revenue across its variety mix
chain = sku_rev.merge(sku_input_mix, on=["sku_code", "brand"], how="inner")
chain["variety_attributed_eur"] = chain["sku_attributed_eur"] * chain["share"]
chain = chain.merge(variety_to_origin, on="variety_code")

origin_rev = (
    chain.groupby("origin_country", as_index=False)["variety_attributed_eur"]
    .sum()
    .sort_values("variety_attributed_eur", ascending=False)
)
print(origin_rev.to_string(index=False))

# %% [markdown]
# ## Result
#
# Each row is "how many EUR of café revenue can be traced back to coffee
# originally grown in that country". The math is approximate, but the *shape*
# of the data is real — and getting from raw event tables to a number like
# this is the everyday job DE/DS people do.
#
# Try refining:
# - Add a real menu→SKU mapping table (could live in `db_pos.menu_to_sku`)
# - Use FIFO inventory accounting instead of proportional shares
# - Aggregate by month and look at how the mix shifts with seasonality
# - Replace pandas with dbt models against DuckDB or the warehouse of your choice
