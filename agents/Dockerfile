FROM ghcr.io/astral-sh/uv:0.12.6 AS uv

FROM python:3.12.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:${PATH}"

COPY --from=uv /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY canonflow_agent ./canonflow_agent
RUN uv sync --frozen --no-dev

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin canonflow
RUN chmod -R a+rX /app

USER 10001

EXPOSE 8080

CMD ["adk", "web", "--host", "0.0.0.0", "--port", "8080", "."]
