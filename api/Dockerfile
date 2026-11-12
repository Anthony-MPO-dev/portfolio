# Chat API. Build from the repository root: docker build -f api/Dockerfile .
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1 PYTHONUNBUFFERED=1
COPY api/pyproject.toml api/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
# The fact search's model (multilingual-e5-small, int8, about 135 MB): pinned to a revision and checked by hash. It
# runs on this server's CPU and never sees anything but the visitor's search question.
ARG E5=https://huggingface.co/Xenova/multilingual-e5-small/resolve/761b726dd34fb83930e26aab4e9ac3899aa1fa78
COPY api/models.sha256 /app/models/multilingual-e5-small/SHA256SUMS
RUN cd /app/models/multilingual-e5-small \
 && python -c "import sys, urllib.request as u; [u.urlretrieve(sys.argv[1] + '/' + f, f.split('/')[-1]) for f in ('onnx/model_quantized.onnx', 'tokenizer.json')]" "$E5" \
 && sha256sum -c SHA256SUMS
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
