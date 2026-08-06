FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy MPLBACKEND=Agg

COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project

COPY src/ ./src/
COPY config/ ./config/
RUN uv sync --no-dev

ENTRYPOINT ["uv", "run", "pyramid"]
CMD ["run-all"]
