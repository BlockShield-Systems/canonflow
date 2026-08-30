FROM ghcr.io/astral-sh/uv:0.12.6 AS uv

FROM python:3.12.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:${PATH}"

COPY --from=uv /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev
RUN chmod -R a+rX /app

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin canonflow
USER 10001

CMD ["mcp-clickhouse"]
