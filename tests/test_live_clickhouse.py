"""Live integration tests. Opt in with BOX_LIVE_TESTS=1.

These are skipped by default because they need the network, and `uvx` to fetch
ClickHouse's published MCP server. They are the tests that prove the judged
integration is real, so they are worth running before a demo:

    BOX_LIVE_TESTS=1 pytest tests/test_live_clickhouse.py -q

They need no credentials. The endpoint is the public ClickHouse SQL playground,
which is what the official `mcp-clickhouse` server points at by default.
"""

from __future__ import annotations

import dataclasses
import os

import pytest

from boxoffice import clickhouse_tools, mcp_clickhouse, queries
from boxoffice.config import settings

pytestmark = pytest.mark.skipif(
    os.getenv("BOX_LIVE_TESTS", "").strip().lower() not in {"1", "true", "yes", "on"},
    reason="live ClickHouse tests are opt-in: set BOX_LIVE_TESTS=1",
)


@pytest.fixture(scope="module", autouse=True)
def _shutdown_session():
    yield
    mcp_clickhouse.shutdown()


def test_official_server_advertises_run_query():
    session = mcp_clickhouse.session()
    assert "run_query" in session.tools
    assert "list_databases" in session.tools


def test_run_query_returns_real_rows_from_clickhouse():
    out = mcp_clickhouse.run_query(
        "SELECT count(*) AS n FROM imdb.movies WHERE year = 1999 AND rank > 0"
    )
    assert out["rows"][0]["n"] > 1000
    assert out["elapsed_ms"] > 0


def test_hero_query_over_mcp_matches_the_offline_snapshot():
    """The same statement, two engines, compared cell by cell."""
    plan = queries.genre_underperformance(1999, 1998)

    offline = clickhouse_tools.run_clickhouse_sql(plan.sql, note=plan.note)
    assert offline["status"] == "ok"

    live_cfg = dataclasses.replace(settings, transport="mcp")
    original = clickhouse_tools.settings
    clickhouse_tools.settings = live_cfg
    try:
        live = clickhouse_tools.run_clickhouse_sql(plan.sql, note=plan.note)
    finally:
        clickhouse_tools.settings = original

    assert live["status"] == "ok", live.get("error")
    assert live["grounding"]["source"] == "clickhouse_mcp"
    assert live["row_count"] == offline["row_count"]
    for a, b in zip(live["rows"], offline["rows"]):
        assert a["genre"] == b["genre"]
        assert a["titles_current"] == b["titles_current"]
        assert a["rating_current"] == pytest.approx(b["rating_current"], abs=1e-9)
        assert a["rating_prior"] == pytest.approx(b["rating_prior"], abs=1e-9)


def test_scope_guardrail_holds_on_the_live_transport():
    live_cfg = dataclasses.replace(settings, transport="mcp")
    original = clickhouse_tools.settings
    clickhouse_tools.settings = live_cfg
    try:
        r = clickhouse_tools.run_clickhouse_sql(
            "SELECT * FROM url('http://169.254.169.254/latest/meta-data/', 'CSV')")
    finally:
        clickhouse_tools.settings = original
    assert r["status"] == "rejected"
    assert r["grounding"]["guardrail"] == "QUERY_SCOPE"
