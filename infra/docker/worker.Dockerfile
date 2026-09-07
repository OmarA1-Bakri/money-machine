FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY config ./config
COPY prompts ./prompts
RUN uv sync --frozen --no-dev

CMD ["python", "-m", "money_machine.orchestration.worker"]

