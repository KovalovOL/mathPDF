FROM dxflrs/garage:v2.5.0 AS garage
FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv

COPY --from=garage /garage /usr/local/bin/garage

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    MATHPDF_CHROMIUM_EXECUTABLE=/usr/bin/chromium

RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-cache
COPY formula_lab ./formula_lab
RUN uv sync --frozen --no-dev --no-editable --no-cache

EXPOSE 8765

CMD ["formula-lab", "--host", "0.0.0.0", "--port", "8765", "--data-dir", "/app/.formula-lab"]
