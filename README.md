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

This is **iteration 1**. Implemented:

- Local infrastructure (Redis, Redpanda + console, MinIO, Postgres) via `docker compose`
- `orchestrator-clock` service — FastAPI app with HTTP control plane and a background ticker that advances simulated time and publishes `clock.tick` events to Redpanda
- `fakecorpo-cli` admin tool — `fakecorpo clock {status,pause,resume,speed,seek}`
- Shared schemas (`fakecorpo_shared.schemas.clock`) — `ClockState`, `ClockTick`

Not yet here: any business-domain simulator (procurement, production, sales-pos, ...), seeders, Railway deployment configs.

## Local quickstart

Requirements: Python 3.12+, Docker.

```bash
# 1) start infra
make up

# 2) install python packages (editable)
make install

# 3) copy and edit env
cp .env.example .env

# 4) run the clock
make clock-run

# 5) in another terminal, talk to it
make cli-status
fakecorpo clock speed 60      # 1 real sec = 1 sim min (slow & easy to watch)
fakecorpo clock pause
fakecorpo clock resume
fakecorpo clock seek 2024-12-24T08:00:00+00:00
```

You'll see ticks flowing into Redpanda. Open the console at <http://localhost:8080> and watch the `clock.tick` topic.

## Clock semantics

- **`speed_ratio`** — how many simulated seconds elapse per real second. `288` means 1 simulated day per 5 real minutes. `1` means real time. `86400` means 1 simulated day per real second (good for backfills).
- **Ticks** are emitted every real `tick_interval_seconds` (default `1.0`). Each tick carries `sim_time`, `real_time`, `speed_ratio`, `paused`. Pause emits ticks with `paused: true` so consumers still see a heartbeat.
- **State persists in Redis.** Restarting the orchestrator continues from where it left off — it does not reset to `INITIAL_SIM_TIME`.

## Configuration

All env vars are documented in [.env.example](./.env.example). The `CLOCK_*` vars configure `orchestrator-clock`; `FAKECORPO_API_URL` configures the CLI.

## Next iterations (planned)

1. `sim-procurement` (NL hub buys green coffee from suppliers, generates POs, contracts, FX, intentional dirty data)
2. `sim-production` (palarnia in Rotterdam roasts batches according to demand, IoT events to Kafka, batch reports to MinIO)
3. `sim-pos-cafes` (3 marki, kawiarnie sprzedają wg sezonowości + pogody, POS events + nightly CSV)
4. `sim-ecommerce`, `sim-b2b`, `sim-marketing`, `sim-finance`, `sim-hr`, `sim-support`
5. Per-brand CRM databases with cross-brand duplicate-customer scenarios
6. Railway deployment manifests (one project, one service per simulator + DBs)
