# Build context expected: repo root (so we can COPY shared/ as well).
# Build:  docker build -f simulators/orchestrator-clock/Dockerfile -t fakecorpo/orchestrator-clock .
# Railway: configure this service's build context as repo root, dockerfile path
#          as simulators/orchestrator-clock/Dockerfile.

FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install shared lib first (changes less often -> better layer caching)
COPY shared/ /app/shared/
RUN pip install /app/shared

# Install service
COPY simulators/orchestrator-clock/ /app/service/
RUN pip install /app/service

EXPOSE 8000
CMD ["uvicorn", "orchestrator_clock.app:app", "--host", "0.0.0.0", "--port", "8000"]
