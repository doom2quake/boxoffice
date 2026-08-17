"""Offline transport: a real SQL engine over a real ClickHouse snapshot.

The point of this module is honesty. An earlier version of BoxOffice Brain
"answered" offline queries by substring-matching the SQL and handing back a
canned row list, which meant ``SELECT count() ... WHERE 1=0`` returned rows. A
grounded-answer agent that fabricates its grounding is worse than useless.

So offline mode now executes the SQL. SQLite (stdlib) is loaded with a
committed snapshot of the *same ClickHouse tables* the live transport queries
(``imdb.movies`` and ``imdb.genres``, restricted to the years the demo asks
about), attached under the schema name ``imdb`` so the identical SQL text runs
in both engines. `WHERE 1=0` returns zero rows here, because it is evaluated.

`scripts/verify_parity.py` runs the hero query through both engines and
compares the numbers, so "offline matches live" is a measurement rather than a
claim. See docs/PARITY.md for the recorded run.

Float note: ClickHouse stores `movies.rank` as Float32 and promotes it to
Float64 when averaging. SQLite only has Float64, so ranks are round-tripped
through a 32-bit float on load. Without that, the two engines disagree in the
7th significant digit.
"""

from __future__ import annotations

import csv
import sqlite3
import struct
import threading
import time
from pathlib import Path
from typing import Any

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
MOVIES_CSV = FIXTURE_DIR / "imdb_movies.csv"
GENRES_CSV = FIXTURE_DIR / "imdb_genres.csv"

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _f32(value: str) -> float:
    """Reproduce ClickHouse Float32 -> Float64 promotion exactly."""
    return struct.unpack("f", struct.pack("f", float(value)))[0]


def _build() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("ATTACH DATABASE ':memory:' AS imdb")
    conn.execute("CREATE TABLE imdb.movies (id INTEGER, name TEXT, year INTEGER, rank REAL)")
    conn.execute("CREATE TABLE imdb.genres (movie_id INTEGER, genre TEXT)")

    with MOVIES_CSV.open(newline="") as fh:
        rows = [(int(r["id"]), r["name"], int(r["year"]), _f32(r["rank"])) for r in csv.DictReader(fh)]
    conn.executemany("INSERT INTO imdb.movies VALUES (?,?,?,?)", rows)

    with GENRES_CSV.open(newline="") as fh:
        grows = [(int(r["movie_id"]), r["genre"]) for r in csv.DictReader(fh)]
    conn.executemany("INSERT INTO imdb.genres VALUES (?,?)", grows)

    conn.commit()
    conn.execute("PRAGMA query_only = ON")  # belt and braces: no writes, ever
    return conn


def connection() -> sqlite3.Connection:
    """Lazily build the snapshot database (process-wide, thread-safe)."""
    global _conn
    with _lock:
        if _conn is None:
            _conn = _build()
        return _conn


def reset() -> None:
    """Drop the cached connection (tests that swap fixtures call this)."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = None


def snapshot_stats() -> dict[str, int]:
    conn = connection()
    return {
        "movies": conn.execute("SELECT count(*) FROM imdb.movies").fetchone()[0],
        "genres": conn.execute("SELECT count(*) FROM imdb.genres").fetchone()[0],
    }


def describe() -> dict[str, list[dict[str, str]]]:
    conn = connection()
    out: dict[str, list[dict[str, str]]] = {}
    for table in ("movies", "genres"):
        cols = conn.execute(f"PRAGMA imdb.table_info({table})").fetchall()
        out[f"imdb.{table}"] = [{"name": c["name"], "type": c["type"]} for c in cols]
    return out


def execute(sql: str, max_rows: int) -> dict[str, Any]:
    """Execute `sql` for real. Returns the same shape as the live transports."""
    conn = connection()
    started = time.monotonic()
    try:
        cur = conn.execute(sql)
    except sqlite3.Error as exc:
        return {
            "status": "error",
            "error": f"offline SQLite engine rejected the query: {exc}",
            "rows": [], "row_count": 0,
            "grounding": {"sql": sql, "source": "offline_snapshot", "error": str(exc)},
        }
    fetched = cur.fetchmany(max_rows + 1)
    truncated = len(fetched) > max_rows
    rows = [dict(r) for r in fetched[:max_rows]]
    cur.close()
    elapsed_ms = round((time.monotonic() - started) * 1000, 1)
    stats = snapshot_stats()
    return {
        "status": "ok", "rows": rows, "row_count": len(rows), "truncated": truncated,
        "grounding": {
            "sql": sql,
            "rows_read": stats["movies"] + stats["genres"],
            "bytes_read": MOVIES_CSV.stat().st_size + GENRES_CSV.stat().st_size,
            "elapsed_ms": elapsed_ms,
            "source": "offline_snapshot",
            "snapshot": f"{stats['movies']} imdb.movies rows + {stats['genres']} imdb.genres rows",
        },
    }
