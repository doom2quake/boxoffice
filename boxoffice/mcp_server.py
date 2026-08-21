"""Serve BoxOffice Brain's GUARDED ClickHouse tools over MCP (stdio).

Run with `python -m boxoffice.mcp_server`. This is NOT the ClickHouse MCP
server; it is the opposite direction. It republishes our own
`run_clickhouse_sql` and `describe_tables` (read-only screen + data-scope
allowlist + rate limiter in front, and whatever transport is configured behind,
including the official ClickHouse MCP server) so another agent can reuse the
guarded surface rather than the raw warehouse.

For the official ClickHouse MCP server, see `boxoffice/mcp_clickhouse.py` and
`boxoffice mcp-check`.

Requires the `mcp` extra.
"""

from __future__ import annotations

from agent_core.mcp import serve_stdio

from .clickhouse_tools import describe_tables, run_clickhouse_sql

if __name__ == "__main__":
    serve_stdio([run_clickhouse_sql, describe_tables], name="boxoffice-guarded-clickhouse")
