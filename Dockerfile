# Container image for the all2md MCP server (stdio transport).
#
# Built from this checkout with the locked dependency set, so the image always
# matches the commit it was built from. Used by the Glama MCP directory
# (glama.json) to run and inspect the server; also usable directly:
#
#   docker build -t all2md-mcp .
#   docker run -i --rm -v "$PWD:/workspace" all2md-mcp
#
# The server reads and writes only inside its working directory (/workspace)
# unless ALL2MD_MCP_ALLOWED_READ_DIRS / ALL2MD_MCP_ALLOWED_WRITE_DIRS say
# otherwise; see docs/source/mcp.rst for every ALL2MD_MCP_* variable.

FROM python:3.13-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first, so source edits do not invalidate this layer.
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --frozen --no-dev --extra mcp --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev --extra mcp --no-editable


FROM python:3.13-slim-bookworm

RUN useradd --create-home --uid 1000 all2md \
    && mkdir /workspace \
    && chown all2md:all2md /workspace

COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER all2md
WORKDIR /workspace

ENTRYPOINT ["all2md-mcp"]
