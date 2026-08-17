# Snapshot provenance

These two CSV files are not invented demo data. They are an extract of the
`imdb` database on the public ClickHouse SQL playground, pulled on
**2026-08-23** from `https://sql-clickhouse.clickhouse.com` (user `demo`, no
password), which is the endpoint the official ClickHouse MCP server points at by
default.

| file              | rows  | query |
|-------------------|-------|-------|
| `imdb_movies.csv` | 4,634 | `SELECT id, name, year, rank FROM imdb.movies WHERE year IN (1998,1999) AND rank > 0 ORDER BY id` |
| `imdb_genres.csv` | 6,605 | `SELECT g.movie_id, g.genre FROM imdb.genres AS g INNER JOIN imdb.movies AS m ON m.id = g.movie_id WHERE m.year IN (1998,1999) AND m.rank > 0 ORDER BY movie_id, genre` |

The full `imdb.movies` table on the playground holds 388,269 rows and
`imdb.roles` holds 3,431,966; this extract is only the slice the demo questions
touch (1998 and 1999 releases with a rating), so the repo stays small.

`boxoffice/offline_engine.py` loads these into an in-memory SQLite database
attached as the schema `imdb`, so the identical SQL text runs offline and live.
`ranks` are round-tripped through a 32-bit float on load to reproduce
ClickHouse's `Float32` storage exactly.

Because this is a subset, an offline question about any year other than 1998 or
1999 legitimately returns zero rows and the agent abstains. That is the intended
behaviour, not a bug: run `BOX_TRANSPORT=mcp` for the full catalogue.

Re-verify at any time with `python scripts/verify_parity.py` (see
`docs/PARITY.md`).
