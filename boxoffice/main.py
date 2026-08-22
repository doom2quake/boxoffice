"""BoxOffice Brain CLI — ask a grounded studio-analytics question.

    boxoffice ask "which genres underperformed in 1999 vs 1998?"
    boxoffice ask "..." --transport mcp     # official ClickHouse MCP server, live
    boxoffice serve                          # local UI + JSON API over the real run
    boxoffice mcp-check                      # prove the official MCP server works

The default transport is `offline`: a real SQLite engine over a committed
snapshot of the same ClickHouse tables, so the pipeline runs anywhere with no
network. `--transport mcp` runs the identical SQL through ClickHouse's own MCP
server against the public ClickHouse SQL playground.

Two rules hold on every path: a number is quoted only if a retrieved row
contains it, and a failed query is reported as a failure, never as "no data".
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from agent_core import StateStore, run_agent, signature_of

from . import clickhouse_tools, queries
from .config import settings
from .clickhouse_tools import run_clickhouse_sql

# One application-scoped store. Building a Firestore client per request was both
# slow and a new empty history every time, which defeats recurrence memory.
_store: StateStore | None = None


def store() -> StateStore:
    global _store
    if _store is None:
        _store = StateStore.create(settings)
    return _store


def reset_store() -> None:
    """Drop the app-scoped store (tests that change settings call this)."""
    global _store
    _store = None


def _fmt_rating(value: Any) -> str:
    return "n/a" if value is None else f"{float(value):.2f}"


def _grounded_answer(question: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    """Route the question to a named query, run it, and ground or abstain.

    Returns a structured result. `abstained` and `error` are set here, not
    inferred from the prose, so the caller never has to grep an answer string.
    """
    try:
        plan = queries.route(question)
    except queries.UnsupportedQuestion as exc:
        supported = "\n  - ".join(queries.SUPPORTED)
        events.append({"kind": "router", "status": "abstain", "label": "no template matches",
                       "detail": str(exc)})
        return {
            "answer": (f"Insufficient comparable data to answer: {exc}.\n"
                       f"Questions this agent can ground:\n  - {supported}"),
            "abstained": True, "error": None, "traces": [], "events": events,
            "query_name": None, "rows": [],
        }

    events.append({"kind": "planner", "status": "ok", "label": f"template {plan.name}",
                   "detail": json.dumps(plan.params)})

    perf = run_clickhouse_sql(plan.sql, note=plan.note)
    events.append({"kind": "analyst", "status": perf["status"], "label": plan.note,
                   "detail": plan.sql, "grounding": perf.get("grounding"),
                   "row_count": perf.get("row_count", 0)})

    # A failed query is an operational error. Reporting it as an empty result
    # would turn a ClickHouse timeout into the conclusion "nothing underperformed".
    if perf["status"] != "ok":
        detail = perf.get("error") or perf.get("reason") or "unknown failure"
        return {
            "answer": (f"Query failed ({perf['status']}): {detail}. "
                       "No answer is given because no rows were retrieved. "
                       "This is an execution error, not a finding about the data."),
            "abstained": True, "error": detail, "traces": [perf.get("grounding")],
            "events": events, "query_name": plan.name, "rows": [],
        }

    rows = perf["rows"]
    if plan.name != "genre_underperformance":
        if not rows:
            return _abstain_no_rows(plan, perf, events)
        lines = [", ".join(f"{k}={_render(v)}" for k, v in r.items()) for r in rows[:10]]
        answer = (f"{plan.note} ({len(rows)} row(s) retrieved):\n  " + "\n  ".join(lines) +
                  f"\nEvery value above is a retrieved ClickHouse row from {perf['grounding']['source']}.")
        return {"answer": answer, "abstained": False, "error": None,
                "traces": [perf.get("grounding")], "events": events,
                "query_name": plan.name, "rows": rows}

    # --- the hero analysis -----------------------------------------------------
    decliners = [r for r in rows if r.get("rating_current") is not None
                 and r.get("rating_prior") is not None
                 and float(r["rating_current"]) < float(r["rating_prior"])]
    if not decliners:
        return _abstain_no_rows(plan, perf, events)

    worst = decliners[0]
    genre = worst["genre"]
    year = plan.params["current_year"]

    signal = run_clickhouse_sql(*_signal_args(genre, year))
    events.append({"kind": "analyst", "status": signal["status"],
                   "label": f"lowest-rated {genre} titles in {year}",
                   "detail": signal["grounding"].get("sql"), "grounding": signal.get("grounding"),
                   "row_count": signal.get("row_count", 0)})

    body = [
        f"{r['genre']}: mean rating {_fmt_rating(r['rating_current'])} in {year} vs "
        f"{_fmt_rating(r['rating_prior'])} in {plan.params['prior_year']} "
        f"(delta {float(r['rating_current']) - float(r['rating_prior']):+.2f}, "
        f"{int(r['titles_current'])} vs {int(r['titles_prior'])} rated titles)"
        for r in decliners[:5]
    ]
    if signal["status"] == "ok" and signal["rows"]:
        drag = "; ".join(f"{r['title']} ({_fmt_rating(r['rating'])})" for r in signal["rows"][:3])
        signal_line = (f"Lowest-rated {genre} titles of {year}: {drag}. "
                       "These titles sit inside the genre and year named above; "
                       "that is an association within the same cohort, not a demonstrated cause.")
    elif signal["status"] == "ok":
        signal_line = f"No {genre} titles for {year} were returned for the detail query."
    else:
        signal_line = (f"Detail query for {genre}/{year} failed "
                       f"({signal.get('error') or signal.get('reason')}); the headline "
                       "comparison above still stands on its own rows.")

    answer = (f"Genres whose mean rating fell from {plan.params['prior_year']} to {year} "
              f"({len(decliners)} of {len(rows)} genres with enough titles):\n  " +
              "\n  ".join(body) +
              f"\nWorst: {genre}.\n" + signal_line)
    events.append({"kind": "answer", "status": "grounded",
                   "label": f"{len(decliners)} declining genres, worst {genre}",
                   "detail": "every number above traces to a retrieved row"})
    return {"answer": answer, "abstained": False, "error": None,
            "traces": [perf.get("grounding"), signal.get("grounding")], "events": events,
            "query_name": plan.name, "rows": decliners}


def _signal_args(genre: str, year: int) -> tuple[str, str]:
    q = queries.genre_worst_titles(genre, year)
    return q.sql, q.note


def _render(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _abstain_no_rows(plan: queries.PlannedQuery, perf: dict[str, Any],
                     events: list[dict[str, Any]]) -> dict[str, Any]:
    events.append({"kind": "answer", "status": "abstain", "label": "0 comparable rows",
                   "detail": "the query executed and returned nothing that answers the question"})
    return {
        "answer": ("Insufficient comparable data to answer: the query ran successfully but "
                   f"returned no rows that answer it ({plan.note}). "
                   f"Needed: {DATA_NEEDED.get(plan.name, 'rows matching the requested period')}."),
        "abstained": True, "error": None, "traces": [perf.get("grounding")], "events": events,
        "query_name": plan.name, "rows": [],
    }


DATA_NEEDED = {
    "genre_underperformance": ("imdb.movies rows with a non-zero rank for both years, joined to "
                               "imdb.genres, with at least the minimum title count per genre"),
    "top_titles": "imdb.movies rows with a non-zero rank for that year",
    "genre_volume": "imdb.movies rows with a non-zero rank for that year, joined to imdb.genres",
    "genre_worst_titles": "imdb.movies rows for that genre and year",
}


async def ask(question: str, use_llm: bool = True) -> dict[str, Any]:
    st = store()
    run_id = st.start_run(trigger={"question": question, "transport": settings.transport})
    tokens = clickhouse_tools.bind_run(
        run_id, guardrail_sink=lambda name, outcome, detail: st.record_guardrail(run_id, name, outcome, detail)
    )
    events: list[dict[str, Any]] = [
        {"kind": "supervisor", "status": "ok", "label": "run started",
         "detail": f"transport={settings.transport} run={run_id}"}
    ]
    try:
        out: dict[str, Any]
        if use_llm:
            try:
                from .agents import root_agent
                result = await run_agent(root_agent, question, app_name=settings.app_name, session_id=run_id)
                answer = result.state.get("grounded_answer") or result.final_text or ""
                out = {
                    "answer": answer,
                    # Derived from the answer that is actually returned, not from
                    # some other field the model happened to emit.
                    "abstained": "insufficient comparable data" in answer.lower(),
                    "error": None,
                    "traces": [result.state.get("analysis_rows")],
                    "events": events + [{"kind": "agent", "status": "ok", "label": "Gemini/ADK graph",
                                         "detail": "supervisor -> planner -> analyst -> answer writer"}],
                    "query_name": "llm", "rows": [],
                }
            except Exception as exc:
                import sys
                print(f"[boxoffice] LLM path unavailable ({exc.__class__.__name__}: {exc}); "
                      "using the keyless grounded router.", file=sys.stderr)
                events.append({"kind": "supervisor", "status": "degraded",
                               "label": "Gemini/ADK unavailable",
                               "detail": f"{exc.__class__.__name__}: {exc}"})
                out = _grounded_answer(question, events)
        else:
            out = _grounded_answer(question, events)

        st.set_data(run_id, "answer", out["answer"])
        st.set_data(run_id, "traces", out["traces"])
        st.set_data(run_id, "abstained", out["abstained"])
        st.detect_recurrence(run_id, signature_of("q", question.lower().strip()))
        st.set_status(run_id, "error" if out.get("error") else "completed", error=out.get("error"))
        doc = st.get(run_id) or {}
        out.update({
            "run_id": run_id,
            "state_backend": st.backend_name,
            "status": doc.get("status"),
            "guardrails": doc.get("guardrails", []),
            "recurrence": doc.get("recurrence"),
            "transport": settings.transport,
            "question": question,
        })
        return out
    except Exception as exc:
        st.fail(run_id, f"{exc.__class__.__name__}: {exc}")
        raise
    finally:
        _run_tok, _sink_tok = tokens
        clickhouse_tools._run_id.reset(_run_tok)
        clickhouse_tools._guardrail_sink.reset(_sink_tok)


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="boxoffice", description="Grounded studio-analytics agent on ClickHouse.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("ask", help="Ask a grounded cinema-analytics question.")
    a.add_argument("question")
    a.add_argument("--no-llm", action="store_true", help="Keyless grounded path (no GCP).")

    s = sub.add_parser("serve", help="Serve the UI and a JSON API backed by real runs.")
    s.add_argument("--port", type=int, default=8765)

    sub.add_parser("mcp-check", help="Start the official ClickHouse MCP server and run one query.")

    args = parser.parse_args(argv)

    if args.cmd == "ask":
        out = asyncio.run(ask(args.question, use_llm=not args.no_llm))
        print("\n" + out["answer"])
        traces = [t for t in out["traces"] if t]
        for t in traces:
            print(f"\n-- {t.get('source')}: rows_read={t.get('rows_read')} "
                  f"bytes_read={t.get('bytes_read')} elapsed_ms={t.get('elapsed_ms')}")
        print(f"\n-- {len(traces)} query trace(s) | abstained={out['abstained']} | "
              f"error={out.get('error')} | run={out['run_id']} | status={out.get('status')} | "
              f"transport={out['transport']} | state={out['state_backend']} | "
              f"guardrails={len(out.get('guardrails', []))}")
        return 0

    if args.cmd == "serve":
        from .server import serve
        serve(args.port)
        return 0

    if args.cmd == "mcp-check":
        from .mcp_check import main as mcp_check_main
        return mcp_check_main()

    return 1


if __name__ == "__main__":
    raise SystemExit(cli())
