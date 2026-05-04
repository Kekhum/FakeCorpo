.PHONY: help up down logs ps restart \
        venv install install-shared install-clock install-cli \
        clock-run cli-status cli-pause cli-resume \
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
	@echo "Infrastructure (docker compose):"
	@echo "  make up           - start redis, redpanda, minio, postgres"
	@echo "  make down         - stop and remove containers"
	@echo "  make logs         - tail container logs"
	@echo "  make ps           - list running containers"
	@echo ""
	@echo "Python install (always into ./$(VENV)):"
	@echo "  make venv         - create the venv (auto-run by install*)"
	@echo "  make install      - install shared + orchestrator-clock + cli (editable)"
	@echo ""
	@echo "Run services:"
	@echo "  make clock-run    - run orchestrator-clock locally on :8000"
	@echo ""
	@echo "Use the CLI:"
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
	$(VENV_PY) -m uvicorn orchestrator_clock.app:app --host 0.0.0.0 --port 8000 --reload

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
