# FakeCorpo

A simulated coffee group running across Europe. Three brands (Bean&Brew IT, NordRoast SE, Café Polonia PL/CZ/SK) sharing a central roastery and procurement, sprawled across a dozen "source systems" producing a continuous stream of messy, realistic enterprise data.

This repo is the **simulator** — the company itself, not the data platform on top. The output (databases, Kafka topics, files in object storage) is the playground for Data Engineers and Data Scientists.

---

## What lives in this repo

```
FakeCorpo/
├── shared/                       Shared Python lib (schemas, helpers)
├── simulators/
│   └── orchestrator-clock/       Global simulation clock (this is the heart)
├── tools/
│   └── fakecorpo-cli/            Admin CLI: control sim speed, pause, seek
├── docker-compose.yml            Local infra: redis, redpanda, minio, postgres
├── Makefile                      Common dev commands
└── .env.example                  Sample env vars
```

## Architecture in one paragraph

A globally-shared **orchestrator-clock** publishes simulated time to a Kafka topic. Every other service ("procurement", "production", "sales-pos", ...) subscribes to that clock and reacts on its own cadence — kupcy podpisują kontrakty, kawiarnie sprzedają, palarnia pali wsady. State lives in per-domain databases (different engines on purpose); events flow through Redpanda; bulk artifacts (CSV, PDF, JSON) land in MinIO. DE/DS people then build their warehouse, dashboards, and ML on top — that's their work, not ours.

## Status

This is **iteration 2** — a 100% local Docker learning environment. Implemented:

- Local infrastructure (Redis, Redpanda + console, MinIO, Postgres) via `docker compose`.
- `orchestrator-clock` — global simulation clock; FastAPI control plane, ticker publishing `clock.tick` to Redpanda.
- `sim-procurement` — first business-domain actor. Subscribes to `clock.tick`. Every simulated week the NL hub picks 1-3 suppliers and places purchase orders for green coffee; every simulated day the arrivals scanner settles in-transit POs (on-time / delayed / very-delayed / lost), runs QC (accepted / partial / rejected), and publishes `procurement.po_created` and `procurement.po_arrived` events. State persists in its own Postgres database `db_procurement`. Master data (10 international suppliers + 12 coffee varieties) seeded on first start.
- `sim-production` — Rotterdam roastery. Subscribes to **two** topics: `clock.tick` and `procurement.po_arrived`. Arrivals credit the green-coffee inventory by variety (one row per variety_code in `green_inventory`, plus an audit log of every movement). Each simulated day the roastery decides 3-8 batches to start, picks SKUs (8 across 3 brands: Bean&Brew, NordRoast, Café Polonia), checks recipes against inventory, and starts batches that have stock. Each batch runs ~12 sim-minutes during which it streams a temperature curve to `production.roaster_telemetry`; on completion, the roastery applies a Gaussian weight loss (~17%) and a cupping score, marks the batch `completed` or `rejected`, and publishes `production.batch_completed`. State persists in `db_production`.
- `sim-pos-cafes` — 15 cafés across 3 brands (Italy/UK + Scandi/NL/DE + PL/CZ/SK), each with a `cafe_type` (office / tourist / hipster / transit) that drives a distinctive demand curve. Subscribes to `clock.tick`, walks one sim-hour at a time, and for each (café, sim-hour) bucket samples a transaction count from `baseline × hour-of-day × day-of-week × season × weather` multipliers. Generates per-transaction line items by category mix (more food at lunch, more iced drinks in summer, etc.) and publishes one `pos.transaction_completed` event per sale. State persists in `db_pos` (`cafes`, `menu_items`, `transactions`, `transaction_lines`, `daily_weather`).
- **Dirty-data layer** in procurement (the meat of the DE/DS exercise): supplier names on invoices that drift from canonical master data (different casing, abbreviations, legal forms — the MDM problem); a chunk of invoices billed in EUR even though contracts are USD, with FX rates that jitter and occasionally go missing; arrivals that come late, very late, or never; QC rejections with realistic reasons. All probabilities are env-tunable (`PROC_P_*`).
- `fakecorpo-cli` admin tool — `fakecorpo clock {status,pause,resume,speed,seek}`.
- Shared schemas (`fakecorpo_shared.schemas`) — `clock.ClockState`, `clock.ClockTick`, `procurement.PurchaseOrderCreated`.

Not yet here: production (palarnia), sales-pos, e-commerce, B2B, finance, HR, support, per-brand CRMs, PDF invoices to MinIO, dirty-data injectors.

## Local quickstart — "the company is alive on my laptop"

Requirements: Docker (with Compose v2). Python 3.12+ only needed if you want to use the CLI from host or do hot-reload dev on the clock.

```bash
# 1) bring up the whole simulated company (infra + simulators)
make up

# 2) watch ticks flow
#    Redpanda Console:  http://localhost:8080  -> Topics -> clock.tick
#    MinIO Console:     http://localhost:9001  (login minioadmin / minioadmin)

# 3) talk to the clock from the CLI (one-time install of the venv-based CLI)
make install
.\.venv\Scripts\fakecorpo.exe clock status                # Windows
./.venv/bin/fakecorpo clock status                        # Linux / macOS

# 4) try the controls
fakecorpo clock speed 60                                  # 1 real sec = 1 sim min
fakecorpo clock pause
fakecorpo clock resume
fakecorpo clock seek 2024-12-24T08:00:00+00:00            # jump to a Christmas morning

# 5) wipe the clock (start over from INITIAL_SIM_TIME) without nuking other data
make clock-reset
docker compose restart orchestrator-clock

# 6) full reset of everything (drops volumes — Redis, Redpanda, MinIO, Postgres)
make reset
```

### Watch the supply chain come alive

After `make up`, all simulators boot, create their databases, seed master data, and wait for clock ticks. With the default speed (288), things move slowly. Bump it for impatient inspection:

```bash
fakecorpo clock speed 86400          # 1 sim-day per real second
make procurement-logs                # watch POs being placed and arrivals settling
make production-logs                 # watch batches start, telemetry stream, completions
make procurement-psql                # poke at suppliers / purchase_orders / po_lines
make production-psql                 # poke at green_inventory / roasting_batches / roasted_inventory
```

In Redpanda Console (<http://localhost:8080>) you'll see seven topics in flight:
`clock.tick` · `procurement.po_created` · `procurement.po_arrived` · `production.batch_started` · `production.batch_completed` · `production.roaster_telemetry` · `pos.transaction_completed` (the last two are high-frequency time-series streams).

### Get to the data faster — DE/DS starter notebooks

Three short tours of the running platform live in [notebooks/](./notebooks/). They show how to connect to all three Postgres databases, do a cross-domain join from supplier to café revenue, and consume events from Redpanda. They're written in jupytext "percent" format (`# %%`-separated cells) so they open as notebooks in Jupyter Lab / VS Code / PyCharm and also run as plain scripts.

```bash
make install-notebooks    # pandas + jupyter + kafka-python into ./.venv
make notebook             # opens Jupyter Lab on ./notebooks
```

See [notebooks/README.md](./notebooks/README.md) for what each notebook covers and ideas for what to do next.

### Hot-reload dev mode for the clock

When you're editing `simulators/orchestrator-clock/` and want instant feedback:

```bash
docker compose stop orchestrator-clock      # free port 8000 / Redis state
make clock-run                              # uvicorn --reload from .venv
```

CLI still works against `http://localhost:8000`.

## Clock semantics

- **`speed_ratio`** — how many simulated seconds elapse per real second. `288` means 1 simulated day per 5 real minutes. `1` means real time. `86400` means 1 simulated day per real second (good for backfills).
- **Ticks** are emitted every real `tick_interval_seconds` (default `1.0`). Each tick carries `sim_time`, `real_time`, `speed_ratio`, `paused`. Pause emits ticks with `paused: true` so consumers still see a heartbeat.
- **State persists in Redis.** Restarting the orchestrator continues from where it left off — it does not reset to `INITIAL_SIM_TIME`.

## Configuration

All env vars are documented in [.env.example](./.env.example). The `CLOCK_*` vars configure `orchestrator-clock`; `FAKECORPO_API_URL` configures the CLI.

## Next iterations (planned)

1. `sim-procurement` extensions: PDF invoices to MinIO, FX volatility, supplier name typos & duplicates, late deliveries, quality rejections (the dirty-data layer).
2. `sim-production` (palarnia in Rotterdam roasts batches according to procurement supply, IoT events to Kafka, batch reports to MinIO).
3. `sim-pos-cafes` (3 marki, kawiarnie sprzedają wg sezonowości + pogody, POS events + nightly CSV).
4. `sim-ecommerce`, `sim-b2b`, `sim-marketing`, `sim-finance`, `sim-hr`, `sim-support`.
5. Per-brand CRM databases with cross-brand duplicate-customer scenarios.
6. A "starter" notebook for DE/DS pointing at the source systems.
