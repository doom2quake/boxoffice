"""BoxOffice Brain tests — keyless, no network, no warehouse.

Every test here pins a specific defect that a review found in the previous
build, so each one fails if the fix is reverted. The transport under test is
`offline`, which is a real SQLite engine over a committed snapshot of the same
ClickHouse tables, so "the query ran" means the query really ran.
"""

import asyncio

import pytest

from boxoffice import clickhouse_tools, main, offline_engine, queries
from boxoffice.clickhouse_tools import describe_tables, run_clickhouse_sql
from boxoffice.config import settings
from boxoffice.main import ask
from boxoffice.sql_guard import assert_query_scope

HERO = "which genres underperformed in 1999 vs 1998?"


@pytest.fixture(autouse=True)
def _clean_run_context(request):
    # A fresh run id per test, so the ActionLimiter's per-cycle budget is not
    # shared between tests (the limiter itself is process-wide by design).
    main.reset_store()
    tok, sink = clickhouse_tools.bind_run(f"test-{request.node.name}")
    yield
    clickhouse_tools._run_id.reset(tok)
    clickhouse_tools._guardrail_sink.reset(sink)


# --- schema / basics ----------------------------------------------------------

def test_describe_tables_lists_the_snapshot_schema():
    r = describe_tables()
    assert r["status"] == "ok"
    assert "imdb.movies" in r["tables"]
    assert {c["name"] for c in r["tables"]["imdb.movies"]} == {"id", "name", "year", "rank"}


def test_snapshot_is_the_real_clickhouse_extract():
    stats = offline_engine.snapshot_stats()
    # Row counts of the extract pulled from sql-clickhouse.clickhouse.com.
    assert stats == {"movies": 4634, "genres": 6605}


# --- guardrail 1: read-only ---------------------------------------------------

def test_read_only_guardrail_rejects_writes():
    r = run_clickhouse_sql("DROP TABLE imdb.movies")
    assert r["status"] == "rejected"
    assert r["grounding"]["guardrail"] == "READ_ONLY_SQL"


# --- guardrail 2: data scope (the hole the review found) ----------------------

@pytest.mark.parametrize("sql", [
    "SELECT * FROM url('http://169.254.169.254/latest/meta-data/', 'CSV')",
    "SELECT * FROM file('/etc/passwd', 'CSV')",
    "SELECT * FROM s3('https://bucket/key', 'CSV')",
    "SELECT * FROM remote('other-host:9000', 'imdb.movies')",
    "SELECT * FROM mysql('h:3306', 'db', 't', 'u', 'p')",
])
def test_table_functions_are_refused(sql):
    r = run_clickhouse_sql(sql)
    assert r["status"] == "rejected", sql
    assert r["grounding"]["guardrail"] == "QUERY_SCOPE"
    assert "table function not allowed" in r["reason"]


def test_out_of_scope_tables_are_refused():
    r = run_clickhouse_sql("SELECT count(*) FROM system.users")
    assert r["status"] == "rejected"
    assert "allowed data scope" in r["reason"]


def test_settings_override_is_refused():
    r = run_clickhouse_sql("SELECT count(*) FROM imdb.movies SETTINGS max_threads = 64")
    assert r["status"] == "rejected"
    assert "SETTINGS" in r["reason"]


def test_comments_cannot_hide_a_blocked_surface():
    # A naive scan over the raw string could be fooled by comment placement.
    sql = "SELECT * FROM /* harmless */ url('http://x/y', 'CSV') -- just a peek"
    assert assert_query_scope(sql, settings.allowed_table_set, "imdb") is not None


def test_allowed_query_passes_the_scope_guard():
    assert assert_query_scope(
        "SELECT g.genre FROM imdb.genres AS g JOIN imdb.movies AS m ON m.id = g.movie_id",
        settings.allowed_table_set, "imdb") is None


def test_cte_names_are_not_mistaken_for_tables():
    sql = ("WITH rated AS (SELECT id, rank FROM imdb.movies WHERE rank > 0) "
           "SELECT count(*) FROM rated")
    assert assert_query_scope(sql, settings.allowed_table_set, "imdb") is None


# --- guardrail 3: action limiter, per-run isolation ---------------------------

def test_spend_guardrail_suppresses_on_dry_run(monkeypatch):
    from agent_core import ActionLimiter, ActionPolicy
    monkeypatch.setattr(clickhouse_tools, "_limiter",
                        ActionLimiter(ActionPolicy(dry_run=True, max_actions_per_cycle=9, max_actions_per_hour=9)))
    r = run_clickhouse_sql("SELECT 1")
    assert r["status"] == "suppressed"


def test_run_id_is_per_context_not_global():
    """Two concurrent runs must not overwrite each other's limiter identity."""
    import threading

    seen = {}

    def worker(name):
        clickhouse_tools.bind_run(name)
        # Give the other thread a chance to clobber a module-global.
        threading.Event().wait(0.05)
        seen[name] = clickhouse_tools.current_run_id()

    threads = [threading.Thread(target=worker, args=(f"run-{i}",)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert seen == {f"run-{i}": f"run-{i}" for i in range(4)}


# --- the offline engine actually executes SQL ---------------------------------

def test_offline_engine_evaluates_predicates():
    """`WHERE 1=0` must return zero rows. The old fixture matcher returned two."""
    r = run_clickhouse_sql("SELECT count(*) AS n FROM imdb.movies WHERE 1=0")
    assert r["status"] == "ok"
    assert r["rows"] == [{"n": 0}]


def test_offline_engine_reports_bad_sql_as_an_error_not_as_no_data():
    r = run_clickhouse_sql("SELECT nonexistent_column FROM imdb.movies")
    assert r["status"] == "error"
    assert r["rows"] == []
    assert "nonexistent_column" in r["error"]


def test_offline_engine_matches_the_recorded_live_numbers():
    """The snapshot reproduces what ClickHouse returned for the hero query.

    These values were read off sql-clickhouse.clickhouse.com and are also
    re-measured by scripts/verify_parity.py; see docs/PARITY.md.
    """
    plan = queries.genre_underperformance(1999, 1998)
    r = run_clickhouse_sql(plan.sql, note=plan.note)
    assert r["status"] == "ok"
    assert r["row_count"] == 18
    worst = r["rows"][0]
    assert worst["genre"] == "War"
    assert worst["rating_current"] == pytest.approx(6.075000005108969, abs=1e-9)
    assert worst["rating_prior"] == pytest.approx(6.858333329359691, abs=1e-9)
    assert worst["titles_current"] == 28 and worst["titles_prior"] == 24


def test_grounding_trace_is_populated():
    r = run_clickhouse_sql("SELECT count(*) AS n FROM imdb.movies", note="row count")
    g = r["grounding"]
    assert g["source"] == "offline_snapshot"
    assert g["transport"] == "offline"
    assert g["note"] == "row count"
    assert isinstance(g["elapsed_ms"], float)


# --- routing: the question must decide the query ------------------------------

def test_router_maps_different_questions_to_different_queries():
    a = queries.route("which genres underperformed in 1999 vs 1998?")
    b = queries.route("what were the best titles of 1998?")
    assert a.name == "genre_underperformance" and b.name == "top_titles"
    assert a.sql != b.sql


def test_router_refuses_a_question_it_cannot_ground():
    with pytest.raises(queries.UnsupportedQuestion):
        queries.route("what was our total APAC streaming revenue last quarter?")


def test_ask_abstains_on_an_unsupported_question():
    """The old fallback answered every question with the canned demo answer."""
    out = asyncio.run(ask("what was our total APAC streaming revenue last quarter?", use_llm=False))
    assert out["abstained"] is True
    assert "Insufficient comparable data" in out["answer"]
    assert "1999" not in out["answer"]  # not the hero answer in disguise
    assert out["traces"] == []


def test_query_templates_escape_values_and_still_fail_closed():
    q = queries.genre_worst_titles("War'; DROP TABLE imdb.movies; --", 1999)
    # 1) the value stays inside one quoted literal: the quote is doubled, so the
    #    statement is still a single SELECT rather than two statements.
    assert "genre = 'War''; DROP TABLE imdb.movies; --'" in q.sql
    assert q.sql.count("SELECT") == 1
    # 2) the read-only screen refuses it anyway. Defence in depth: an escaped
    #    payload is inert, and we still decline to send it.
    r = run_clickhouse_sql(q.sql)
    assert r["status"] == "rejected"
    assert r["grounding"]["guardrail"] == "READ_ONLY_SQL"


def test_normal_genre_values_are_not_refused():
    r = run_clickhouse_sql(queries.genre_worst_titles("War", 1999).sql)
    assert r["status"] == "ok"
    assert r["rows"][0]["title"] == "Active Stealth"


# --- the end-to-end grounded and abstain paths --------------------------------

def test_ask_grounded_end_to_end():
    out = asyncio.run(ask(HERO, use_llm=False))
    assert out["abstained"] is False
    assert out["error"] is None
    assert "War" in out["answer"]
    assert "6.08" in out["answer"] and "6.86" in out["answer"]
    assert len([t for t in out["traces"] if t]) == 2


def test_correlated_signal_is_scoped_to_the_named_genre_and_year():
    """The old build pulled a global 'most negative' row and called it correlated."""
    out = asyncio.run(ask(HERO, use_llm=False))
    signal_sql = out["traces"][1]["sql"]
    assert "g.genre = 'War'" in signal_sql
    assert "m.year = 1999" in signal_sql
    assert "not a demonstrated cause" in out["answer"]


def test_abstains_when_the_period_has_no_rows():
    out = asyncio.run(ask("which genres underperformed in 2021 vs 2020?", use_llm=False))
    assert out["abstained"] is True
    assert "Insufficient comparable data" in out["answer"]
    assert out["error"] is None


def test_query_failure_is_not_reported_as_no_data(monkeypatch):
    """A ClickHouse timeout used to be answered as 'no Q3 titles'."""
    def boom(sql, max_rows):
        return {"status": "error", "error": "Read timed out", "rows": [], "row_count": 0,
                "grounding": {"sql": sql, "source": "clickhouse_http", "error": "Read timed out"}}

    monkeypatch.setattr(offline_engine, "execute", boom)
    out = asyncio.run(ask(HERO, use_llm=False))
    assert out["error"] == "Read timed out"
    assert out["abstained"] is True
    assert "execution error" in out["answer"]
    assert "underperformed" not in out["answer"].lower()


# --- run lifecycle and audit trail --------------------------------------------

def test_run_is_finalised_and_guardrails_are_persisted():
    out = asyncio.run(ask(HERO, use_llm=False))
    assert out["status"] == "completed"
    names = {g["name"] for g in out["guardrails"]}
    assert names == {"READ_ONLY_SQL", "QUERY_SCOPE", "ACTION_LIMITER"}
    assert all(g["outcome"] == "pass" for g in out["guardrails"])
    doc = main.store().get(out["run_id"])
    assert doc["status"] == "completed"
    assert doc["data"]["abstained"] is False


def test_store_is_application_scoped_so_history_survives():
    """A per-request store made recurrence memory permanently empty."""
    first = asyncio.run(ask(HERO, use_llm=False))
    second = asyncio.run(ask(HERO, use_llm=False))
    assert main.store() is main.store()
    assert second["recurrence"] is not None
    assert second["recurrence"]["count"] >= 2
    assert first["run_id"] in second["recurrence"]["prior_run_ids"]


def test_guardrail_rejection_is_recorded_on_the_run():
    st = main.store()
    run_id = st.start_run(trigger={"question": "injected"})
    tok, sink = clickhouse_tools.bind_run(
        run_id, guardrail_sink=lambda n, o, d: st.record_guardrail(run_id, n, o, d))
    try:
        run_clickhouse_sql("SELECT * FROM url('http://x/y', 'CSV')")
    finally:
        clickhouse_tools._run_id.reset(tok)
        clickhouse_tools._guardrail_sink.reset(sink)
    guards = st.get(run_id)["guardrails"]
    assert [g["outcome"] for g in guards if g["name"] == "QUERY_SCOPE"] == ["rejected"]


# --- the official MCP integration fails closed --------------------------------

def test_official_mcp_client_targets_clickhouses_own_server():
    from boxoffice import mcp_clickhouse
    command, args = mcp_clickhouse.server_command()
    assert "mcp-clickhouse" in args
    env = mcp_clickhouse.server_env()
    assert env["CLICKHOUSE_HOST"] == settings.clickhouse_host
    assert env["CLICKHOUSE_READ_ONLY"] == "true"
    assert mcp_clickhouse.RUN_QUERY_TOOL == "run_query"


def test_mcp_transport_fails_closed_when_the_server_is_missing(monkeypatch):
    """It must surface an error, never silently downgrade to in-process tools."""
    import dataclasses

    from boxoffice import mcp_clickhouse

    monkeypatch.setattr(clickhouse_tools, "settings", dataclasses.replace(settings, transport="mcp"))

    def unavailable(sql, cfg=None):
        raise mcp_clickhouse.McpUnavailable("uvx not found")

    monkeypatch.setattr(mcp_clickhouse, "run_query", unavailable)
    r = run_clickhouse_sql("SELECT count(*) AS n FROM imdb.movies")
    assert r["status"] == "error"
    assert "uvx not found" in r["error"]
    assert r["rows"] == []


def test_mcp_session_start_raises_rather_than_returning_none():
    """A broken launcher must raise, not return None and fall back silently."""
    import dataclasses

    from boxoffice import mcp_clickhouse

    mcp_clickhouse.shutdown()
    broken = dataclasses.replace(settings, mcp_command="definitely-not-a-real-binary",
                                 mcp_startup_timeout_s=10)
    try:
        with pytest.raises(mcp_clickhouse.McpUnavailable):
            mcp_clickhouse.session(broken)
    finally:
        mcp_clickhouse.shutdown()


# --- the UI carries real captured output, and says which mode it is in --------

def test_ui_transcript_is_generated_from_real_runs():
    import json
    import re
    from pathlib import Path

    ui = (Path(__file__).resolve().parents[1] / "boxoffice" / "ui" / "index.html").read_text()
    m = re.search(r"var TRANSCRIPT = (\{.*?\});\n", ui, re.S)
    assert m, "no recorded transcript embedded; run scripts/record_transcript.py"
    data = json.loads(m.group(1))
    grounded = data["scenarios"]["grounded"]["result"]
    assert grounded["abstained"] is False
    assert grounded["run_id"].startswith("run-")
    assert grounded["traces"][0]["source"] in {"offline_snapshot", "clickhouse_mcp", "clickhouse_http"}
    # The refusals shown in the UI are real tool results, not written copy.
    assert data["guardrail"]["injection"]["result"]["status"] == "rejected"
    # And the page must label a replay as a replay.
    assert "recorded transcript, not live" in ui.lower()
