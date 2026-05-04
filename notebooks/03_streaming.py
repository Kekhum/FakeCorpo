# %% [markdown]
# # 03 — Streaming taste: read events from Redpanda
#
# Up to now we've queried Postgres — the **state** view of each domain. This
# notebook reads the **event** view: the same operations as they happen,
# delivered through Kafka topics on the Redpanda broker at `localhost:19092`.
#
# Every simulator publishes events as it acts:
#
# | topic | published by | what it is |
# |---|---|---|
# | `clock.tick` | orchestrator-clock | heartbeat, every real second |
# | `procurement.po_created` | sim-procurement | new PO with supplier + invoice details |
# | `procurement.po_arrived` | sim-procurement | shipment settled (incl. quality) |
# | `production.batch_started` | sim-production | new roasting batch charged |
# | `production.batch_completed` | sim-production | batch done with weight-loss + cupping |
# | `production.roaster_telemetry` | sim-production | drum/exhaust temps, ~6/min per batch |
# | `pos.transaction_completed` | sim-pos-cafes | one event per café sale |
#
# Make sure the clock is running before you run this — paused clock means no
# new events.

# %%
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")  # safe no-op in Jupyter; fixes Windows console
except Exception:
    pass

import json
from collections import Counter
from datetime import datetime
from kafka import KafkaConsumer

BROKERS = "localhost:19092"


def sip(topic: str, seconds: float = 5.0, group_suffix: str = "explore"):
    """Read up to `seconds` of events from a topic, then stop.

    Uses a one-shot consumer group (so each run gets fresh events from the
    `latest` offset rather than catching up from the beginning).
    """
    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=BROKERS,
        auto_offset_reset="latest",
        group_id=f"notebook-{group_suffix}-{int(datetime.now().timestamp())}",
        consumer_timeout_ms=int(seconds * 1000),
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    out = []
    for msg in consumer:
        out.append(msg.value)
    consumer.close()
    return out

# %% [markdown]
# ## Heartbeat — the simulation clock

# %%
ticks = sip("clock.tick", seconds=3.0, group_suffix="ticks")
print(f"Captured {len(ticks)} ticks in 3 seconds.")
for ev in ticks[:3]:
    print(f"  sim_time={ev['sim_time']}  speed={ev['speed_ratio']}  paused={ev['paused']}")

# %% [markdown]
# ## POS transactions — the front line
#
# Each event is a complete sale: café, brand, sim-time, lines, weather snapshot,
# payment method. Self-contained — a downstream consumer can act without
# touching the POS database.

# %%
sales = sip("pos.transaction_completed", seconds=5.0, group_suffix="sales")
print(f"Captured {len(sales)} sales in 5 seconds.")
if sales:
    sample = sales[0]
    print("\nExample event:")
    print(json.dumps(sample, indent=2))

# %% [markdown]
# Let's aggregate over the captured window — what categories were trending
# in this slice?

# %%
if sales:
    by_brand = Counter(s["brand"] for s in sales)
    print("\nBy brand:")
    for b, n in by_brand.most_common():
        print(f"  {b}: {n}")

    line_categories = Counter(
        line["category"] for s in sales for line in s["lines"]
    )
    print("\nBy line category:")
    for c, n in line_categories.most_common():
        print(f"  {c}: {n}")

    by_weather = Counter(s["weather_condition"] for s in sales)
    print("\nBy weather (in the live window):")
    for w, n in by_weather.most_common():
        print(f"  {w}: {n}")

# %% [markdown]
# ## Roaster telemetry — high-frequency time-series
#
# When a batch is in progress, samples flow ~every 10 sim-seconds. At the
# default sim speed that's tens to hundreds of events per real second; a real
# streaming pipeline would window these and detect anomalies in the curve.

# %%
samples = sip("production.roaster_telemetry", seconds=4.0, group_suffix="telemetry")
print(f"Captured {len(samples)} telemetry samples in 4 seconds.")
if samples:
    # Group by batch and show min/max temperatures observed
    batches: dict[int, list[float]] = {}
    for s in samples:
        batches.setdefault(s["batch_id"], []).append(s["drum_temp_celsius"])

    print("\nDrum temperature range per batch in this window:")
    for bid, temps in list(batches.items())[:5]:
        print(f"  batch {bid}: {min(temps):.1f}°C – {max(temps):.1f}°C ({len(temps)} samples)")

# %% [markdown]
# ## What this enables
#
# A few real DE/DS exercises you can build from here:
#
# - Aggregate hourly POS revenue by brand in real time using `KafkaConsumer`
#   plus a sliding window — same pipeline you'd later port to ksqlDB or
#   Bytewax or Flink.
# - Detect roaster anomalies — drum temp spike outside the curve envelope
#   should fire an alert.
# - Replay events into a fresh DuckDB / ClickHouse / DataLake to test ELT
#   pipelines from scratch with full reproducibility (the same seed +
#   sim-time produces the same events).
