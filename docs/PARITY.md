# Parity: the same query, three engines, compared

`scripts/verify_parity.py` runs one statement, byte for byte identical, through
all three transports and compares every returned cell. It exits non-zero if any
pair disagrees, and writes `docs/parity.json`.

The statement is the hero query (`queries.genre_underperformance(1999, 1998)`):
mean IMDb rating per genre in 1999 against 1998, over `imdb.genres` joined to
`imdb.movies`, restricted to genres with at least 20 rated titles in both years.

## Recorded run, 2026-08-23

    python scripts/verify_parity.py

| transport | source            | rows | wall ms | engine ms | rows read | bytes read |
|-----------|-------------------|------|---------|-----------|-----------|------------|
| offline   | offline_snapshot  | 18   | 104.6   | 17.7      | 11,239    | 244,796    |
| http      | clickhouse_http   | 18   | 387.6   | 387.1     | 783,388   | 9,835,115  |
| mcp       | clickhouse_mcp    | 18   | 5,446.5 | 1,032.3   | n/a       | n/a        |

    offline vs http: IDENTICAL
    offline vs mcp:  IDENTICAL
    http vs mcp:     IDENTICAL

All 18 rows and every numeric cell matched to within 1e-9 across the three
engines.

## Reading the numbers honestly

* **The offline snapshot is not faster than ClickHouse.** It reads 11,239 rows
  because that is all the snapshot holds; the live warehouse reads 783,388 rows
  of `imdb.genres` and `imdb.movies` for the same answer. Comparing the two
  latencies would be comparing a 245 KB extract against a real table scan.
* **The MCP wall time includes starting the server.** The 5.4 s figure is the
  first call in a fresh process, which includes `uvx` resolving and launching
  `mcp-clickhouse`. The session is then held open, so subsequent tool calls are
  the ~0.6 to 1.0 s you see in the UI. The `engine_ms` column is the tool call
  itself, not the startup.
* **MCP reports no scan statistics.** The official server's `run_query` returns
  columns and rows only, so `rows_read` and `bytes_read` are genuinely
  unavailable on that path and the UI prints `n/a` rather than a made-up number.
  Use `BOX_TRANSPORT=http` when you want the scan counters.
* **1e-9 agreement needed one deliberate fix.** ClickHouse stores
  `imdb.movies.rank` as `Float32` and promotes it to `Float64` when averaging.
  SQLite has only `Float64`, so the snapshot loader round-trips each rank
  through a 32-bit float (`offline_engine._f32`). Without that the two engines
  disagree in the seventh significant digit and this table would read
  "DIFFERS".

## What this does and does not prove

It proves the offline demo is not a hand-written mock: it computes the same
answer from the same data as the live warehouse. It does not prove anything
about ClickHouse's performance at scale, and it is not a benchmark. It is a
correctness check on our own offline path.
