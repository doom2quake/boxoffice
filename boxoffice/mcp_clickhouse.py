"""Client for the OFFICIAL ClickHouse MCP server (`mcp-clickhouse`).

This is the load-bearing partner integration, and it is a real one: we launch
ClickHouse's own published MCP server over stdio, list its tools, and call its
`run_query` tool. We do not wrap our own functions and call that "MCP".

The server is started as `uvx --python 3.11 mcp-clickhouse` and configured
through the environment variables it documents (CLICKHOUSE_HOST / PORT / USER /
PASSWORD / SECURE). With the shipped defaults that is the public ClickHouse SQL
playground, so the MCP path is demonstrable without a funded key.

Fail-closed contract: if the transport is `mcp` and the server cannot be
started or the tool call fails, every function here RAISES `McpUnavailable`.
Nothing silently downgrades to in-process tools; the caller decides.

One long-lived session is kept on a background event loop, because spawning
`uvx` per query costs seconds and would make the demo look slower than
ClickHouse actually is.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from typing import Any

from .config import BoxOfficeSettings, settings

#: The tool name the official server exposes for running SQL.
RUN_QUERY_TOOL = "run_query"
EXPECTED_TOOLS = ("list_databases", "list_tables", RUN_QUERY_TOOL)


class McpUnavailable(RuntimeError):
    """The official ClickHouse MCP server could not be used."""


def server_env(cfg: BoxOfficeSettings | None = None) -> dict[str, str]:
    """Environment for `mcp-clickhouse`, per its documented configuration."""
    cfg = cfg or settings
    env = dict(os.environ)
    env.update({
        "CLICKHOUSE_HOST": cfg.clickhouse_host,
        "CLICKHOUSE_PORT": str(cfg.clickhouse_port),
        "CLICKHOUSE_USER": cfg.clickhouse_user,
        "CLICKHOUSE_PASSWORD": cfg.clickhouse_password,
        "CLICKHOUSE_SECURE": "true" if cfg.clickhouse_secure else "false",
        "CLICKHOUSE_VERIFY": "true",
        "CLICKHOUSE_DATABASE": cfg.clickhouse_database,
        "CLICKHOUSE_READ_ONLY": "true",
    })
    return env


def server_command(cfg: BoxOfficeSettings | None = None) -> tuple[str, list[str]]:
    cfg = cfg or settings
    return cfg.mcp_command, [a for a in cfg.mcp_args.split(",") if a]


# --- background session ------------------------------------------------------

class _Session:
    """Owns one stdio MCP session on its own asyncio loop in a daemon thread."""

    def __init__(self, cfg: BoxOfficeSettings) -> None:
        self.cfg = cfg
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._stop: asyncio.Event | None = None
        self._session: Any = None
        self._error: BaseException | None = None
        self.tools: list[str] = []

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="boxoffice-mcp", daemon=True)
        self._thread.start()
        if not self._ready.wait(self.cfg.mcp_startup_timeout_s):
            raise McpUnavailable(
                f"official ClickHouse MCP server did not start within "
                f"{self.cfg.mcp_startup_timeout_s}s ({' '.join((server_command(self.cfg)[0],) + tuple(server_command(self.cfg)[1]))})"
            )
        if self._error is not None:
            raise McpUnavailable(f"official ClickHouse MCP server unavailable: {self._error}")

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._serve())
        except BaseException as exc:  # noqa: BLE001 - surfaced to start()
            self._error = exc
            self._ready.set()
        finally:
            try:
                loop.close()
            except Exception:  # pragma: no cover
                pass

    async def _serve(self) -> None:
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except Exception as exc:  # pragma: no cover - optional dep
            raise McpUnavailable(f"the `mcp` package is not installed: {exc}") from exc

        command, args = server_command(self.cfg)
        params = StdioServerParameters(command=command, args=args, env=server_env(self.cfg))
        self._stop = asyncio.Event()
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listing = await session.list_tools()
                self.tools = [t.name for t in listing.tools]
                if RUN_QUERY_TOOL not in self.tools:
                    raise McpUnavailable(
                        f"official ClickHouse MCP server exposes {self.tools!r}, "
                        f"which does not include {RUN_QUERY_TOOL!r}"
                    )
                self._session = session
                self._ready.set()
                await self._stop.wait()

    def call(self, tool: str, arguments: dict[str, Any], timeout: float) -> str:
        if self._session is None or self._loop is None:
            raise McpUnavailable("MCP session is not running")
        future = asyncio.run_coroutine_threadsafe(
            self._session.call_tool(tool, arguments), self._loop
        )
        try:
            result = future.result(timeout=timeout)
        except Exception as exc:  # noqa: BLE001
            raise McpUnavailable(f"MCP tool {tool!r} failed: {exc}") from exc
        parts = [getattr(c, "text", "") for c in (result.content or [])]
        return "\n".join(p for p in parts if p)

    def close(self) -> None:
        if self._loop is not None and self._stop is not None:
            self._loop.call_soon_threadsafe(self._stop.set)
        self._session = None


_session: _Session | None = None
_session_lock = threading.Lock()


def session(cfg: BoxOfficeSettings | None = None) -> _Session:
    """Return the running MCP session, starting the official server if needed."""
    global _session
    cfg = cfg or settings
    with _session_lock:
        if _session is None:
            candidate = _Session(cfg)
            candidate.start()  # raises McpUnavailable
            _session = candidate
        return _session


def shutdown() -> None:
    global _session
    with _session_lock:
        if _session is not None:
            _session.close()
        _session = None


# --- the tool call ------------------------------------------------------------

def run_query(sql: str, cfg: BoxOfficeSettings | None = None) -> dict[str, Any]:
    """Call the official server's `run_query` tool. Raises `McpUnavailable`.

    The server answers with ``{"columns": [...], "rows": [[...]]}`` on success
    and a plain error string otherwise, so a non-JSON body is treated as a
    query error rather than being silently read as "no rows".
    """
    cfg = cfg or settings
    sess = session(cfg)
    started = time.monotonic()
    text = sess.call(RUN_QUERY_TOOL, {"query": sql}, timeout=cfg.http_timeout_s + 15)
    elapsed_ms = round((time.monotonic() - started) * 1000, 1)
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise McpUnavailable(f"ClickHouse MCP run_query returned an error: {text[:400]}") from exc
    if not isinstance(payload, dict) or "columns" not in payload or "rows" not in payload:
        raise McpUnavailable(f"unexpected run_query payload: {text[:400]}")
    columns = payload["columns"]
    rows = [dict(zip(columns, r)) for r in payload["rows"]]
    return {"rows": rows, "elapsed_ms": elapsed_ms, "tools": list(sess.tools)}


# --- ADK toolset (the agent consumes the same official server) ----------------

def official_mcp_toolset(cfg: BoxOfficeSettings | None = None):
    """An ADK `McpToolset` bound to the official ClickHouse MCP server.

    Raises `McpUnavailable` rather than returning None: if the judged
    integration is requested and cannot be built, the run must fail loudly.
    """
    cfg = cfg or settings
    try:
        from google.adk.tools.mcp_tool import McpToolset
        from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
        from mcp import StdioServerParameters
    except Exception as exc:  # pragma: no cover - optional deps
        raise McpUnavailable(f"google-adk with the MCP extra is required: {exc}") from exc

    command, args = server_command(cfg)
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(command=command, args=args, env=server_env(cfg)),
            timeout=float(cfg.mcp_startup_timeout_s),
        ),
        tool_filter=list(EXPECTED_TOOLS),
    )
