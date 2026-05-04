# FakeCorpo — DE/DS starter notebooks

Three short tours of what's running on your laptop. The simulators write into
Postgres + Redpanda continuously while the clock ticks; these notebooks show
how to read it back.

| | |
|---|---|
| `01_explore.py` | Connect to all 3 source databases, get a feel for scale, look at the dirty-data layer in the wild |
| `02_supply_chain.py` | The full Bean → Batch → Café join — cross-database pandas merge that traces every cup back to its supplier |
| `03_streaming.py` | Sip from the Kafka topics for a few seconds — clock heartbeats, real-time POS transactions, roaster telemetry |

## Setup (one time)

```bash
make install-notebooks    # adds pandas, jupyter, kafka-python etc. to ./.venv
```

## Running

Three options, all equivalent:

```bash
make notebook                                       # open Jupyter Lab on this folder
.\.venv\Scripts\python.exe notebooks/01_explore.py  # plain script
.\.venv\Scripts\jupytext --to ipynb notebooks/*.py  # convert to .ipynb if you prefer
```

The files are written in **jupytext "percent" format** — `# %%` is a code-cell
boundary, `# %% [markdown]` opens a markdown cell. VS Code's Python extension,
PyCharm, and Jupyter Lab (with the jupytext extension) all render them as
notebooks; running them as plain scripts also works.

## Before you run them

Make sure the stack is up and the clock has run for a while — empty databases
are boring:

```bash
make up
fakecorpo clock speed 86400    # backfill: 1 sim-day per real-second
# wait ~30 seconds for material data to accumulate
fakecorpo clock pause          # optional, freezes the snapshot for queries
```

## Where to go next

Try these on your own:
- Build a daily revenue table per (café, day) joining `transactions` × `cafes`
- Cluster suppliers by their on-time arrival rate vs total spend
- Train a forecaster for hourly transactions using day-of-week + weather
- Detect supplier-name duplicates with rapidfuzz / record linkage
- Spin up dbt + DuckDB and replicate the cross-domain join from notebook 02
