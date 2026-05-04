FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY shared/ /app/shared/
RUN pip install /app/shared

COPY simulators/sim-pos-cafes/ /app/service/
RUN pip install /app/service

CMD ["python", "-m", "sim_pos_cafes"]
