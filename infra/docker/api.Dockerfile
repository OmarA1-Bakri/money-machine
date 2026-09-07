FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY config ./config
COPY prompts ./prompts
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
RUN uv sync --frozen --no-dev

EXPOSE 8000
CMD ["uvicorn", "money_machine.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

