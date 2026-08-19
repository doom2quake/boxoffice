"""ClickHouse tools — the agent's only route to data, and its guardrail.

Every query passes four gates before a byte leaves the process:

  1. READ_ONLY_SQL   single SELECT/WITH, no writes or DDL (agent-core).
  2. QUERY_SCOPE     no table functions, no SETTINGS, and every table on an
                     explicit allowlist (`sql_guard`). This is what stops a
                     prompt-injected `SELECT * FROM url(...)`.
  3. ACTION_LIMITER  per-run and per-hour caps (agent-core), keyed off a
                     ContextVar so concurrent runs cannot steal each other's
                     budget.
  4. SERVER BOUNDS   ClickHouse-side `max_result_rows`, `max_result_bytes`,
                     `max_execution_time` and `readonly=1`, plus a bounded
                     client read, so an unbounded generated query is stopped by
                     the server rather than by our process running out of RAM.

Then it runs on the configured transport: the official ClickHouse MCP server,
ClickHouse's HTTP interface, or the offline SQLite snapshot. Every result
carries a grounding trace (SQL, rows read, bytes read, latency, source) and a
`status`. `status == "ok"` is the ONLY value a caller may read rows from.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from contextvars import ContextVar
from typing import Any, Callable

from agent_core import ActionLimiter, ActionPolicy, assert_read_only

from . import mcp_clickhouse, offline_engine
from .config import settings
from .sql_guard import assert_query_scope

_limiter = ActionLimiter(ActionPolicy.from_env("BOX"))

# Per-run identity. A ContextVar (not a module global) so two concurrent asks
# are rate-limited independently instead of overwriting each other.
_run_id: ContextVar[str] = ContextVar("boxoffice_run_id", default="adhoc")

#: Optional sink for guardrail decisions: (name, outcome, detail).
_guardrail_sink: ContextVar[Callable[[str, str, str], None] | None] = ContextVar(
    "boxoffice_guardrail_sink", default=None
)


def bind_run(run_id: str, guardrail_sink: Callable[[str, str, str], None] | None = None):
    """Bind the current context to a run. Returns the ContextVar tokens."""
    return (_run_id.set(run_id or "adhoc"), _guardrail_sink.set(guardrail_sink))


def current_run_id() -> str:
    return _run_id.get()


def _record(name: str, outcome: str, detail: str = "") -> None:
    sink = _guardrail_sink.get()
    if sink is not None:
        try:
            sink(name, outcome, detail)
        except Exception:  # pragma: no cover - audit must never break a run
            pass


def describe_tables() -> dict[str, Any]:
    """List the ClickHouse cinema tables the agent may read, with their columns.

    Call this first so the SQL you write uses real column names. Returns a dict
    of ``db.table -> [{name, type}, ...]``.
    """
    if settings.is_offline:
        return {"status": "ok", "tables": offline_engine.describe(),
                "grounding": {"source": "offline_snapshot"}}
    allowed = sorted(t for t in settings.allowed_table_set if not t.startswith("system."))
    names = ", ".join(f"'{t.split('.', 1)[1]}'" for t in allowed)
    dbs = ", ".join(sorted({f"'{t.split('.', 1)[0]}'" for t in allowed}))
    sql = (f"SELECT database, table, name, type FROM system.columns "
           f"WHERE database IN ({dbs}) AND table IN ({names}) ORDER BY database, table, position")
    res = run_clickhouse_sql(sql, note="warehouse schema")
    if res.get("status") != "ok":
        return {"status": res.get("status"), "error": res.get("error") or res.get("reason"),
                "tables": {}, "grounding": res.get("grounding")}
    schema: dict[str, list] = {}
    for row in res.get("rows", []):
        schema.setdefault(f"{row.get('database')}.{row.get('table')}", []).append(
            {"name": row.get("name"), "type": row.get("type")}
        )
    return {"status": "ok", "tables": schema, "grounding": res.get("grounding")}


def run_clickhouse_sql(sql: str, note: str = "") -> dict[str, Any]:
    """Run a READ-ONLY ClickHouse query and return rows plus a grounding trace.

    Args:
        sql: one SELECT/WITH statement over the allowed cinema tables.
        note: short description of what this query is for (shown in the trace).

    Returns a dict with ``status`` (ok | rejected | suppressed | error), ``rows``,
    ``row_count`` and ``grounding`` (sql, rows_read, bytes_read, elapsed_ms,
    source). Only read ``rows`` when ``status == "ok"``.
    """
    err = assert_read_only(sql)
    if err:
        _record("READ_ONLY_SQL", "rejected", err)
        return {"status": "rejected", "reason": err, "rows": [], "row_count": 0,
                "grounding": {"sql": sql, "guardrail": "READ_ONLY_SQL", "reason": err}}
    _record("READ_ONLY_SQL", "pass", note or "single read-only statement")

    scope_err = assert_query_scope(sql, settings.allowed_table_set, settings.clickhouse_database)
    if scope_err:
        _record("QUERY_SCOPE", "rejected", scope_err)
        return {"status": "rejected", "reason": scope_err, "rows": [], "row_count": 0,
                "grounding": {"sql": sql, "guardrail": "QUERY_SCOPE", "reason": scope_err}}
    _record("QUERY_SCOPE", "pass", f"tables within {sorted(settings.allowed_table_set)[:3]}...")

    allowed, reason = _limiter.check(_run_id.get(), "clickhouse_query")
    if not allowed:
        _record("ACTION_LIMITER", "suppressed", reason)
        return {"status": "suppressed", "reason": reason, "rows": [], "row_count": 0,
                "grounding": {"sql": sql, "guardrail": "ACTION_LIMITER", "reason": reason}}
    _record("ACTION_LIMITER", "pass", reason)

    if settings.is_offline:
        result = offline_engine.execute(sql, settings.max_rows)
    elif settings.transport == "mcp":
        result = _run_via_official_mcp(sql)
    else:
        result = _run_via_http(sql)

    grounding = result.setdefault("grounding", {})
    grounding.setdefault("sql", sql)
    grounding["note"] = note
    grounding["transport"] = settings.transport
    return result


# --- transports ---------------------------------------------------------------

def _run_via_official_mcp(sql: str) -> dict[str, Any]:
    """Execute through the official ClickHouse MCP server. Fails closed."""
    try:
        out = mcp_clickhouse.run_query(sql)
    except mcp_clickhouse.McpUnavailable as exc:
        return {"status": "error", "error": str(exc), "rows": [], "row_count": 0,
                "grounding": {"sql": sql, "source": "clickhouse_mcp", "error": str(exc)}}
    rows = out["rows"][: settings.max_rows]
    return {
        "status": "ok", "rows": rows, "row_count": len(rows),
        "truncated": len(out["rows"]) > settings.max_rows,
        "grounding": {
            "sql": sql, "elapsed_ms": out["elapsed_ms"], "source": "clickhouse_mcp",
            "mcp_server": "mcp-clickhouse (official)", "mcp_tool": mcp_clickhouse.RUN_QUERY_TOOL,
            "mcp_tools_available": out["tools"], "endpoint": settings.clickhouse_url,
            # The official server's run_query returns columns+rows only, so
            # rows_read / bytes_read are genuinely unavailable on this path. Use
            # BOX_TRANSPORT=http for scan statistics. We would rather show a
            # blank than a made-up number.
            "rows_read": None, "bytes_read": None,
            "stats_note": "run_query does not return ClickHouse scan statistics",
        },
    }


def _run_via_http(sql: str) -> dict[str, Any]:
    """Execute over ClickHouse's HTTP interface with server-side bounds."""
    params = urllib.parse.urlencode({
        "user": settings.clickhouse_user,
        "database": settings.clickhouse_database,
        "default_format": "JSON",
        # Bound the work on the SERVER. `result_overflow_mode=break` makes
        # ClickHouse stop producing rows instead of erroring, so an unbounded
        # generated query costs a capped amount rather than a warehouse bill.
        "readonly": "1",
        "max_result_rows": str(settings.max_rows),
        "max_result_bytes": str(settings.max_result_bytes),
        "result_overflow_mode": "break",
        "max_execution_time": str(settings.max_execution_time_s),
    })
    url = f"{settings.clickhouse_url}?{params}"
    headers = {"Content-Type": "text/plain"}
    if settings.clickhouse_password:
        headers["X-ClickHouse-Key"] = settings.clickhouse_password
        headers["X-ClickHouse-User"] = settings.clickhouse_user

    started = time.monotonic()
    try:
        req = urllib.request.Request(url, data=sql.encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=settings.http_timeout_s) as resp:  # noqa: S310
            # Bounded read: never decode more than max_result_bytes (+1 to detect
            # the overflow) regardless of what the server sends back.
            raw = resp.read(settings.max_result_bytes + 1)
        if len(raw) > settings.max_result_bytes:
            msg = f"response exceeded BOX_MAX_RESULT_BYTES ({settings.max_result_bytes}); refused"
            return {"status": "error", "error": msg, "rows": [], "row_count": 0,
                    "grounding": {"sql": sql, "source": "clickhouse_http", "error": msg}}
        payload = json.loads(raw.decode())
    except Exception as exc:
        return {"status": "error", "error": str(exc), "rows": [], "row_count": 0,
                "grounding": {"sql": sql, "source": "clickhouse_http", "error": str(exc)}}

    elapsed_ms = round((time.monotonic() - started) * 1000, 1)
    all_rows = payload.get("data", [])
    rows = all_rows[: settings.max_rows]
    stats = payload.get("statistics", {})
    return {
        "status": "ok", "rows": rows, "row_count": len(rows),
        "truncated": len(all_rows) > settings.max_rows,
        "grounding": {
            "sql": sql, "rows_read": stats.get("rows_read"), "bytes_read": stats.get("bytes_read"),
            "elapsed_ms": elapsed_ms, "server_elapsed_s": stats.get("elapsed"),
            "source": "clickhouse_http", "endpoint": settings.clickhouse_url,
        },
    }
