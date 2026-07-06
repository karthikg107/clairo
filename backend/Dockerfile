FROM python:3.12-slim AS base

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Dependencies layer (cached unless requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App source + Alembic (migrations must ship in the image — the start
# command below runs them on every boot, since hosts without a distinct
# "release phase" step, e.g. Render's free tier, have nowhere else to run them)
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Non-root user
RUN addgroup --system clairo && adduser --system --ingroup clairo clairo
USER clairo

EXPOSE 8000

# $PORT is platform-assigned on hosts like Render/Railway; defaults to 8000
# for `docker run` without one set.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD sh -c 'curl -f http://localhost:${PORT:-8000}/api/v1/health || exit 1'

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]

# ── Development stage ────────────────────────────────────────────────────────
FROM base AS dev
USER root
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
USER clairo
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
