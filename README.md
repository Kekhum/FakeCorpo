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

This is **iteration 1** — a 100% local Docker learning environment. Implemented:

- Local infrastructure (Redis, Redpanda + console, MinIO, Postgres) via `docker compose`
- `orchestrator-clock` service — FastAPI app with HTTP control plane and a background ticker that advances simulated time and publishes `clock.tick` events to Redpanda. Runs as a compose service (default) or locally with hot reload (dev).
- `fakecorpo-cli` admin tool — `fakecorpo clock {status,pause,resume,speed,seek}`
- Shared schemas (`fakecorpo_shared.schemas.clock`) — `ClockState`, `ClockTick`

Not yet here: any business-domain simulator (procurement, production, sales-pos, ...), seeders, per-brand CRM databases.

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

1. `sim-procurement` (NL hub buys green coffee from suppliers, generates POs, contracts, FX, intentional dirty data)
2. `sim-production` (palarnia in Rotterdam roasts batches according to demand, IoT events to Kafka, batch reports to MinIO)
3. `sim-pos-cafes` (3 marki, kawiarnie sprzedają wg sezonowości + pogody, POS events + nightly CSV)
4. `sim-ecommerce`, `sim-b2b`, `sim-marketing`, `sim-finance`, `sim-hr`, `sim-support`
5. Per-brand CRM databases with cross-brand duplicate-customer scenarios
6. A "starter" notebook for DE/DS pointing at the source systems
