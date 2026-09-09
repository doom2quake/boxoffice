# BoxOffice Brain — hosted demo for the Agentic Cinema hackathon
# (ClickHouse + Google Cloud track). Runs the REAL pipeline: `boxoffice serve`
# answers /api/ask from live ClickHouse, and `boxoffice mcp-check` launches the
# official ClickHouse MCP server (`uvx mcp-clickhouse`) on the same instance.
FROM python:3.11-slim

# `uv`/`uvx` are needed at RUNTIME: the official ClickHouse MCP server is
# launched as `uvx --python 3.11 mcp-clickhouse`. Copy the standalone binaries
# from the published uv image and put them on PATH.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Copy the self-contained app (agent_core is vendored in-tree).
COPY . /app

# Install the app with the MCP client extra, plus the Google AI stack
# (google-adk / google-genai) so the Gemini/Vertex path is importable on the
# instance. The deterministic grounded router needs none of these; they make
# the LLM path available without being on the first-click critical path.
RUN pip install --no-cache-dir ".[mcp]" google-adk google-genai

# Pre-fetch the official ClickHouse MCP server into the uv cache so `mcp-check`
# does not pay the download cost on its first call at demo time.
RUN uvx --python 3.11 mcp-clickhouse --help >/dev/null 2>&1 || true

# Cloud Run provides $PORT (8080). The server binds 0.0.0.0:$PORT.
ENV PORT=8080
EXPOSE 8080

CMD ["boxoffice", "serve"]
