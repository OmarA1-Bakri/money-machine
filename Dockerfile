FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    EXTERNAL_ACTIONS_ENABLED=false

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev

EXPOSE 8000
CMD ["uvicorn", "money_machine.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
