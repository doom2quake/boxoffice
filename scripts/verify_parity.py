"""Measure the three transports against each other on the identical SQL.

Why this exists: "the offline demo shows the same numbers as the live warehouse"
is the kind of claim a judge should be able to falsify. So we do not assert it,
we measure it. The same statement text is executed by

  * the offline SQLite snapshot,
  * ClickHouse's HTTP interface,
  * ClickHouse's own MCP server (`mcp-clickhouse`, `run_query`),

and the returned values are compared cell by cell. The script prints a table
and writes docs/parity.json. It exits non-zero if any pair disagrees.

    python scripts/verify_parity.py                 # all three
    python scripts/verify_parity.py --transports offline

Network is required for `http` and `mcp`; `uvx` is required for `mcp`. Skipping
a transport is reported as skipped, never as a pass.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from boxoffice import queries  # noqa: E402

TOLERANCE = 1e-9


def _run(transport: str, sql: str) -> dict:
    """Execute `sql` on one transport in a clean settings context."""
    import importlib
    import os

    os.environ["BOX_TRANSPORT"] = transport
    os.environ.setdefault("BOX_IN_MEMORY_STATE", "true")
    import boxoffice.config as config

    importlib.reload(config)
    import boxoffice.clickhouse_tools as tools

    importlib.reload(tools)
    started = time.monotonic()
    result = tools.run_clickhouse_sql(sql, note="parity check")
    result["wall_ms"] = round((time.monotonic() - started) * 1000, 1)
    return result


def _cells(rows: list[dict]) -> list[list]:
    return [[r[k] for k in sorted(r)] for r in rows]


def _compare(a: list[dict], b: list[dict]) -> list[str]:
    diffs: list[str] = []
    if len(a) != len(b):
        diffs.append(f"row count {len(a)} != {len(b)}")
        return diffs
    for i, (ra, rb) in enumerate(zip(_cells(a), _cells(b))):
        for j, (va, vb) in enumerate(zip(ra, rb)):
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)) \
                    and not isinstance(va, bool) and not isinstance(vb, bool):
                if abs(float(va) - float(vb)) > TOLERANCE:
                    diffs.append(f"row {i} col {j}: {va} != {vb}")
            elif str(va) != str(vb):
                diffs.append(f"row {i} col {j}: {va!r} != {vb!r}")
    return diffs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--transports", default="offline,http,mcp")
    ap.add_argument("--out", default=str(REPO / "docs" / "parity.json"))
    args = ap.parse_args(argv)

    plan = queries.genre_underperformance(1999, 1998)
    wanted = [t.strip() for t in args.transports.split(",") if t.strip()]

    results: dict[str, dict] = {}
    for transport in wanted:
        print(f"--- {transport} ---")
        try:
            res = _run(transport, plan.sql)
        except Exception as exc:  # noqa: BLE001
            print(f"  SKIPPED: {exc.__class__.__name__}: {exc}")
            results[transport] = {"status": "skipped", "error": f"{exc.__class__.__name__}: {exc}"}
            continue
        if res["status"] != "ok":
            print(f"  SKIPPED: status={res['status']} {res.get('error') or res.get('reason')}")
            results[transport] = {"status": "skipped", "error": res.get("error") or res.get("reason")}
            continue
        g = res["grounding"]
        print(f"  rows={res['row_count']} wall_ms={res['wall_ms']} "
              f"engine_ms={g.get('elapsed_ms')} rows_read={g.get('rows_read')} "
              f"bytes_read={g.get('bytes_read')}")
        results[transport] = {
            "status": "ok", "row_count": res["row_count"], "rows": res["rows"],
            "wall_ms": res["wall_ms"], "engine_ms": g.get("elapsed_ms"),
            "rows_read": g.get("rows_read"), "bytes_read": g.get("bytes_read"),
            "source": g.get("source"),
        }

    ok = [t for t, r in results.items() if r.get("status") == "ok"]
    comparisons = []
    failed = False
    for i in range(len(ok)):
        for j in range(i + 1, len(ok)):
            a, b = ok[i], ok[j]
            diffs = _compare(results[a]["rows"], results[b]["rows"])
            comparisons.append({"a": a, "b": b, "identical": not diffs, "diffs": diffs[:20]})
            verdict = "IDENTICAL" if not diffs else f"DIFFERS ({len(diffs)})"
            print(f"{a} vs {b}: {verdict}")
            for d in diffs[:5]:
                print(f"    {d}")
            failed = failed or bool(diffs)

    if len(ok) < 2:
        print("\nOnly one transport ran; parity was NOT verified in this run.")

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "query": dataclasses.asdict(plan),
        "tolerance": TOLERANCE,
        "transports": {t: {k: v for k, v in r.items() if k != "rows"} for t, r in results.items()},
        "row_counts": {t: r.get("row_count") for t, r in results.items()},
        "comparisons": comparisons,
        "verified": bool(comparisons) and not failed,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    print(f"\nwrote {out}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
