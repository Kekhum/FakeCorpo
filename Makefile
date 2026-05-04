.PHONY: help up down logs ps restart rebuild reset \
        venv install install-shared install-clock install-cli \
        clock-run clock-logs clock-reset \
        cli-status cli-pause cli-resume \
        test clean

# ---------- venv config ----------
# We isolate Python deps in .venv so `make install` never touches system Python.
VENV := .venv

ifeq ($(OS),Windows_NT)
    VENV_PY  := $(VENV)/Scripts/python.exe
    VENV_BIN := $(VENV)/Scripts
else
    VENV_PY  := $(VENV)/bin/python
    VENV_BIN := $(VENV)/bin
endif

# system Python used only to bootstrap the venv
PY ?= python

help:
	@echo "FakeCorpo - common dev commands"
	@echo ""
	@echo "Run the whole simulated company (default mode):"
	@echo "  make up           - start everything (infra + simulators)"
	@echo "  make down         - stop and remove containers"
	@echo "  make logs         - tail all container logs"
	@echo "  make ps           - list running containers"
	@echo "  make rebuild      - rebuild simulator images after code changes"
	@echo "  make reset        - DROP all sim state (volumes + containers) and restart fresh"
	@echo ""
	@echo "Hot-reload dev for the clock (instead of running it in compose):"
	@echo "  make install      - install shared + clock + cli into local .venv"
	@echo "  make clock-run    - run orchestrator-clock locally with --reload on :8000"
	@echo "                      (stop the compose 'orchestrator-clock' service first)"
	@echo "  make clock-logs   - tail logs of the compose orchestrator-clock service"
	@echo "  make clock-reset  - clear ONLY the clock state in Redis (sim restarts from"
	@echo "                      INITIAL_SIM_TIME on next tick), without touching other data"
	@echo ""
	@echo "CLI (talks to whichever clock is on :8000):"
	@echo "  make cli-status   - show current sim clock state"
	@echo "  make cli-pause    - pause the simulation"
	@echo "  make cli-resume   - resume the simulation"
	@echo ""
	@echo "Test:"
	@echo "  make test         - run pytest across packages"

# ---------- Infra ----------

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

ps:
	docker compose ps

restart: down up

rebuild:
	docker compose build orchestrator-clock
	docker compose up -d orchestrator-clock

reset:
	@echo "Tearing down all containers AND volumes — this wipes Redis, Redpanda, MinIO, Postgres."
	docker compose down -v
	docker compose up -d --build

# ---------- venv ----------
# Create venv only if missing; idempotent
$(VENV_PY):
	$(PY) -m venv $(VENV)
	$(VENV_PY) -m pip install --upgrade pip

venv: $(VENV_PY)

# ---------- Python install ----------

install: install-shared install-clock install-cli

install-shared: $(VENV_PY)
	$(VENV_PY) -m pip install -e ./shared

install-clock: $(VENV_PY)
	$(VENV_PY) -m pip install -e "./simulators/orchestrator-clock[test]"

install-cli: $(VENV_PY)
	$(VENV_PY) -m pip install -e ./tools/fakecorpo-cli

# ---------- Run ----------

clock-run: $(VENV_PY)
	$(VENV_PY) -m uvicorn orchestrator_clock.app:app --host 0.0.0.0 --port 8000 --reload \
	    --app-dir simulators/orchestrator-clock/src

clock-logs:
	docker compose logs -f --tail=100 orchestrator-clock

clock-reset:
	docker compose exec redis redis-cli DEL clock:state clock:tick_id
	@echo "Clock state cleared. Restart the orchestrator-clock to seed from INITIAL_SIM_TIME:"
	@echo "  docker compose restart orchestrator-clock"

cli-status:
	$(VENV_BIN)/fakecorpo clock status

cli-pause:
	$(VENV_BIN)/fakecorpo clock pause

cli-resume:
	$(VENV_BIN)/fakecorpo clock resume

# ---------- Test / clean ----------

test: $(VENV_PY)
	$(VENV_PY) -m pytest -q simulators/orchestrator-clock/tests

clean:
	@echo "Removing build artifacts (keeping $(VENV) and docker volumes)"
	@find . -type d -name __pycache__ -not -path "./$(VENV)/*" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info"  -not -path "./$(VENV)/*" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -not -path "./$(VENV)/*" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache"   -not -path "./$(VENV)/*" -exec rm -rf {} + 2>/dev/null || true
