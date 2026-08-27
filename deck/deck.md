---
marp: true
theme: uncover
paginate: true
backgroundColor: #0B0B0C
color: #F2F1EC
style: |
  section { font-family: -apple-system, system-ui, sans-serif; }
  h1, h2 { color: #F2F1EC; letter-spacing: -0.02em; }
  strong { color: #FFD634; }
  em { color: #46C98B; font-style: normal; }
  code { background: #101012; color: #FFD634; }
  a { color: #FFD634; }
  table { font-size: 0.75em; }
  .muted { color: #9A9A92; }
  .bad { color: #E5484D; }
---

<!-- _class: lead -->
# BoxOffice Brain

### Ask a cinema question. Get a number a row backs, or an honest "I cannot."

<span class="muted">doom2quake · Agentic Cinema 2026 · ClickHouse track</span>

---

## The problem

An analyst asks: *which genres underperformed in 1999 versus 1998?*

Text-to-analytics agents answer **confidently**. You cannot tell a grounded
"War fell 0.78 rating points" from a **hallucinated one.**

And a summary over a cached extract is already wrong the moment the warehouse moves.

---

## The second problem nobody demos

An agent that writes its own SQL will eventually write:

```sql
SELECT * FROM url('http://169.254.169.254/latest/meta-data/', 'CSV')
```

That is a **single read-only SELECT**. It reads the cloud metadata endpoint.

<span class="muted">Read-only is necessary. It is nowhere near sufficient.</span>

---

## The idea

Quote a number **only** when a ClickHouse row supports it.

Show the **evidence**: the SQL, rows read, bytes scanned, latency.

When the rows cannot answer, *abstain* and name the missing data.
When the query **fails**, say it failed. <span class="bad">Never call a timeout "no data".</span>

Bound what the generated SQL can reach with an **allowlist**, not with hope.

---

## ClickHouse's own MCP server does the work

```
$ boxoffice mcp-check
launching official ClickHouse MCP server: uvx --python 3.11 mcp-clickhouse
endpoint: https://sql-clickhouse.clickhouse.com:8443/ (user=demo)
tools advertised: ['list_databases', 'list_tables', 'run_query']
tool call: run_query   latency: 1030.7 ms   rows: 5
```

Not our wrapper with an MCP-shaped name. **`mcp-clickhouse`**, ClickHouse's package.

<span class="muted">No credentials: the public ClickHouse SQL playground, 388,269 films.</span>

---

## Three transports, one statement

| `BOX_TRANSPORT` | runs the SQL | needs |
|---|---|---|
| `mcp` | official ClickHouse MCP server → ClickHouse | `uvx` |
| `http` | ClickHouse HTTP, same SQL, no MCP hop | network |
| `offline` | SQLite over a committed extract of the same tables | nothing |

Offline **executes** the SQL. `WHERE 1=0` returns zero rows.

---

## So parity can be measured, not claimed

```
$ python scripts/verify_parity.py
offline vs http: IDENTICAL
offline vs mcp:  IDENTICAL
http vs mcp:     IDENTICAL
```

18 rows, every numeric cell within **1e-9**.

<span class="muted">Needed a Float32 round-trip on load, or the engines split in the 7th digit.</span>

---

## The guardrails, on real return values

```
SELECT * FROM url('http://169.254.169.254/...')
  -> rejected: table function not allowed: url()
SELECT count(*) FROM system.users
  -> rejected: table not in the allowed data scope: system.users
DROP TABLE imdb.movies
  -> rejected: only SELECT/WITH queries are allowed
```

Every decision is persisted on the run and shown in the UI's audit trail.

---

## The demo

1. `boxoffice mcp-check`, the sponsor integration, provably running.
2. `BOX_TRANSPORT=mcp boxoffice serve`, banner reads **LIVE**, Ask runs it.
3. Second query is filtered to the genre the first one named. *Cohort, not a global row.*
4. Ask about 2021: query runs, no rows, **abstains**. Ask about APAC revenue: no template, **abstains**.
5. Guardrail tab: three real refusals.

<span class="muted">Opened as a file it turns amber: "recorded transcript, not live".</span>

---

## Proven

**35** keyless tests · **4** live tests against ClickHouse's MCP server.

Data-scope allowlist · offline engine evaluates predicates · failed query is not
"no data" · signal scoped to the named cohort · MCP **fails closed** ·
UI transcript came from a real run.

---

## What we do not claim

Gemini and ADK are wired; **no funded Vertex project on this build**, so every
number here came from the keyless router, not a model run.

Snapshot covers 1998 to 1999. Live endpoint is a public playground.
**No holdout evaluation yet.**

<span class="muted">All of it written down in HONESTY.md.</span>

---

<!-- _class: lead -->
## BoxOffice Brain

<span class="muted">github.com/doom2quake/boxoffice</span>
