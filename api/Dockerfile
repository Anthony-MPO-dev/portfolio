# Chat API. Build from the repository root: docker build -f api/Dockerfile .
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1 PYTHONUNBUFFERED=1
COPY api/pyproject.toml api/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY api/app ./app
COPY knowledge/facts.md ./knowledge/facts.md
RUN useradd --create-home --uid 10001 api
USER api
ENV PATH="/app/.venv/bin:$PATH" FACTS_PATH=/app/knowledge/facts.md \
    FORWARDED_ALLOW_IPS=10.0.0.0/8,172.16.0.0/12,192.168.0.0/16
EXPOSE 8000
# Trust X-Forwarded-For only from the private Docker networks (Easypanel's Traefik), walked from the right, so a
# visitor can't forge it. No access log: it would hold IPs.
CMD ["uvicorn", "app.main:app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-access-log"]
