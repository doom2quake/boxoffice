# Demo script

Six minutes, no credentials, no paid keys. Everything below has been run
end to end on a clean machine; the captured output is in `docs/`.

## Setup (once)

```bash
pip install -e ../../packages/agent-core
pip install -e '.[mcp]'
```

`uvx` (from `uv`) is needed for the live ClickHouse MCP server. Nothing else.

## 0. The claim (20 s)

"BoxOffice Brain answers a studio question by writing ClickHouse SQL, running it
through ClickHouse's own MCP server, and quoting only numbers that came back in
a row. If the rows cannot answer, it says so."

## 1. Prove the sponsor integration is real (60 s)

```bash
boxoffice mcp-check
```

This launches `uvx --python 3.11 mcp-clickhouse`, ClickHouse's published MCP
server, prints the tools it advertises, then calls `run_query`:

```
tools advertised: ['list_databases', 'list_tables', 'run_query']
tool call: run_query
latency: 1030.7 ms
rows: 5
  {"genre": "Drama", "titles": 809, "rating": 6.1368356025115816}
  ...
```

Point at the tool list. Those names are the server's, not ours. Full capture:
`docs/live-proof.txt`.

## 2. The hero question, live (90 s)

```bash
BOX_TRANSPORT=mcp boxoffice serve
```

Open `http://127.0.0.1:8765`. The banner is green and says LIVE with the
endpoint. Press **Ask**.

What to point at, in order:

1. **Step 1** names the query template the question routed to.
2. **Step 2** is the exact SQL. It is the SQL that ran, not a rendering of it.
3. The **grounding trace** line under it: source `clickhouse_mcp`, latency.
4. **Step 3** is the second query, and it is filtered to the genre and year the
   first query named. The agent looks for the drag inside the cohort it just
   found, not at a global row.
5. **Step 4** is the answer. Every number in it appears in a row above.
6. **Agent activity log**, right column: the guardrail audit trail persisted on
   the run. `READ_ONLY_SQL pass`, `QUERY_SCOPE pass`, `ACTION_LIMITER allowed
   (1/4 this cycle)`.

## 3. The abstain (45 s)

Pick the second question, "which genres underperformed in 2021 versus 2020?",
with the transport switched to offline:

```bash
boxoffice serve            # default transport is offline
```

The query runs, returns nothing, and the agent abstains and names the data it
would need. Then pick the third question, about APAC streaming revenue: no
template matches, so it abstains before touching the warehouse and lists what it
can answer. Neither one invents a number.

## 4. The guardrail (45 s)

Pick the fourth entry, **Guardrail**. Three real tool return values:

```
SELECT * FROM url('http://169.254.169.254/latest/meta-data/', 'CSV')
  -> rejected: table function not allowed: url()
SELECT count(*) FROM system.users
  -> rejected: table not in the allowed data scope: system.users
DROP TABLE imdb.movies
  -> rejected: only SELECT/WITH queries are allowed
```

That first one is the cloud metadata endpoint. A read-only SELECT is not enough
to stop it; the data-scope allowlist is.

## 5. Parity, the part that is measured (60 s)

```bash
python scripts/verify_parity.py
```

One statement, three engines, every cell compared:

```
offline vs http: IDENTICAL
offline vs mcp:  IDENTICAL
http vs mcp:     IDENTICAL
```

So the offline demo is not a mock. `docs/PARITY.md` has the table and the
caveats, including why the latencies are not comparable.

## 6. Tests (30 s)

```bash
BOX_IN_MEMORY_STATE=true pytest tests -q          # 35 passed
BOX_LIVE_TESTS=1 pytest tests/test_live_clickhouse.py -q   # 4 passed, needs network
```

## Close

`HONESTY.md` lists what is not demonstrated: Gemini and ADK are wired but every
number here came from the keyless router, there is no funded Vertex project on
this build, and there is no holdout evaluation yet.
