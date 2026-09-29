# Ein Image für API, Worker und Migrationsjob (Plan 6.2: Worker = gleiches Image)
FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# Debian-Sicherheitsupdates einspielen, die das offizielle Python-Image noch nicht enthält (Trivy in CI);
# dazu die Systembibliotheken von WeasyPrint (Steckbrief als PDF, Modul G3) und eine Schrift mit den
# nötigen Zeichen; dazu Tesseract mit Französisch für gescannte PDFs (AN7, docs/PLAN_AN7_SCAN.md). Alles gehört
# in `base`, damit Tests und Worker dasselbe Verhalten haben.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libfribidi0 fonts-dejavu-core \
        tesseract-ocr tesseract-ocr-fra \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv
WORKDIR /app

FROM base AS dev
# Entwicklung und Tests: mit Dev-Abhängigkeiten, Quellcode per Volume
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS runtime
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
# Dateiverzeichnis (EMPRISE_FILES_DIR): ein frisches Docker-Volume übernimmt Eigentümer und Rechte von hier
RUN useradd --system --uid 10001 --home-dir /app emprise     && mkdir -p /data/files && chown 10001:10001 /data/files
USER 10001
ARG RELEASE=dev
ENV EMPRISE_RELEASE=${RELEASE}
EXPOSE 8000
# Proxy-Köpfe nur vom vorgeschalteten Web-Container im privaten Netz (FORWARDED_ALLOW_IPS)
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-server-header"]
