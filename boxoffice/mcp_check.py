"""`boxoffice mcp-check` — prove the official ClickHouse MCP server really runs.

Starts `mcp-clickhouse` (ClickHouse's own published MCP server) over stdio,
lists the tools it advertises, calls its `run_query` tool, and prints the rows
and the latency. Exits non-zero if any of that fails, so it is usable as a
smoke test in CI as well as on stage.

Requires network (it fetches the server via `uvx` and reaches ClickHouse). With
the shipped defaults it needs no credentials: it talks to the public ClickHouse
SQL playground, which is the same endpoint the official server defaults to.
"""

from __future__ import annotations

import json
import sys
import time

from . import mcp_clickhouse
from .config import settings

PROOF_SQL = (
    "SELECT g.genre AS genre, count(*) AS titles, avg(m.rank) AS rating "
    "FROM imdb.genres AS g INNER JOIN imdb.movies AS m ON m.id = g.movie_id "
    "WHERE m.year = 1999 AND m.rank > 0 GROUP BY g.genre ORDER BY titles DESC LIMIT 5"
)


def main(argv: list[str] | None = None) -> int:
    command, args = mcp_clickhouse.server_command()
    print(f"launching official ClickHouse MCP server: {command} {' '.join(args)}")
    print(f"endpoint: {settings.clickhouse_url} (user={settings.clickhouse_user})")
    started = time.monotonic()
    try:
        session = mcp_clickhouse.session()
    except mcp_clickhouse.McpUnavailable as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    print(f"server up in {time.monotonic() - started:.1f}s")
    print(f"tools advertised: {session.tools}")

    try:
        out = mcp_clickhouse.run_query(PROOF_SQL)
    except mcp_clickhouse.McpUnavailable as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 3
    finally:
        pass

    print(f"\ntool call: {mcp_clickhouse.RUN_QUERY_TOOL}")
    print(f"sql: {PROOF_SQL}")
    print(f"latency: {out['elapsed_ms']} ms")
    print(f"rows: {len(out['rows'])}")
    for row in out["rows"]:
        print("  " + json.dumps(row))
    mcp_clickhouse.shutdown()
    return 0 if out["rows"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
