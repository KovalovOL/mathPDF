FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    MATHPDF_CHROMIUM_EXECUTABLE=/usr/bin/chromium

RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
COPY formula_lab ./formula_lab
COPY main.pdf ./main.pdf
RUN uv sync --frozen --no-dev --no-editable --no-cache

EXPOSE 8765

CMD ["formula-lab", "--host", "0.0.0.0", "--port", "8765", "--pdf", "/app/main.pdf", "--data-dir", "/app/.formula-lab"]
