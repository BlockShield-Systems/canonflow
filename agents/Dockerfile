# ---------- stage 1: static frontend (Next.js static export) ----------
FROM node:22.17.1-bookworm-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build && test -f out/index.html

# ---------- stage 2: python runtime ----------
FROM ghcr.io/astral-sh/uv:0.12.6 AS uv

FROM python:3.12.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    PATH="/app/.venv/bin:${PATH}"

COPY --from=uv /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY canonflow_agent ./canonflow_agent
COPY serve.py ./
RUN uv sync --frozen --no-dev

# The frozen run snapshot ships inside the package; the bundle comes from stage 1.
COPY --from=web /web/out ./canonflow_agent/ui/web

RUN test -f canonflow_agent/ui/snapshot/index.json \
 && test -f canonflow_agent/ui/web/index.html \
 && python -c "import json,pathlib;d=json.loads(pathlib.Path('canonflow_agent/ui/snapshot/index.json').read_text());print('snapshot beats:',len(d['beats']))"

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin canonflow
RUN chmod -R a+rX /app

USER 10001

EXPOSE 8080

CMD ["python", "serve.py"]
