# BoxOffice Brain — Devpost submission

Agentic Cinema: The Blockbuster Hackathon, ClickHouse track. Gemini + Google ADK
over the official ClickHouse MCP server.

## Elevator pitch

Explore a what-if film. BoxOffice Brain projects it against the real crowd of
comparable titles in ClickHouse, and Gemini narrates the story of where it would
land, with the chart to prove every number. Flip through parallel universes of
years and genres. It never invents a figure, and when the data is too thin it
says so.

**Tagline: it runs real ClickHouse SQL, and it will not invent a box-office number.**

## The problem

A studio or distributor analyst can already query a warehouse. What they cannot do
is walk into a greenlight meeting with a read they can defend. General-purpose LLMs
narrate confident, invented numbers, and a bare SQL result is a wall of rows with no
story. The pain is not "writing SQL is hard". It is "I need a defensible read of how
this idea would land, and I cannot trust a number a model might have made up".

## What it does

BoxOffice Brain is a data-backed multiverse projector for film ideas. You pose a
what-if (a genre and a year, or a plain-English scenario), and:

1. it pulls the real cohort of comparable titles from ClickHouse and shows them as a
   living crowd settling on the rating axis, with the real mean, spread and range;
2. **Gemini reads that real cohort and tells you the story** of where the idea would
   land, in plain language, using only the numbers the database returned;
3. you explore parallel universes on the multiverse rail, the same scenario across
   years and across genres, and the crowd and the story re-form as you go;
4. when a cohort is too thin to project, it abstains and says so instead of inventing
   a shape.

A second tab, "Ask the data", is the direct path: ask a question in plain English and
Gemini writes one read-only SQL statement, runs it through the official ClickHouse MCP
server, and answers only with rows that came back. Every dot, line, number and
sentence traces to a real row. The refusal to invent is the product, not a caveat.

## How we built it

- **Google Cloud, at runtime.** Gemini (`gemini-2.5-flash`) on Vertex AI, driven
  by a Google ADK supervisor plus three skills (planner, analyst, answer writer),
  assembled from our reusable `agent-core`. Gemini writes the SQL and calls the
  MCP tool itself; a captured end-to-end run is in `docs/gemini-run.txt`.
- **ClickHouse, at runtime, through its own MCP server.** `BOX_TRANSPORT=mcp`
  launches `uvx --python 3.11 mcp-clickhouse`, the server ClickHouse publishes,
  and every query goes through its `run_query` tool. `boxoffice mcp-check` prints
  the tools the server advertises (`list_databases`, `list_tables`, `run_query`)
  and a real call with latency and rows (`docs/live-proof.txt`). It is ClickHouse's
  own server, not a wrapper of ours with an MCP-shaped name.
- **Three transports, one SQL statement.** `mcp` (via the MCP server), `http`
  (ClickHouse HTTP, same SQL, for scan statistics), and `offline` (SQLite over a
  committed real extract, so the demo runs with nothing installed). A parity check
  (`scripts/verify_parity.py`) proves all three return identical rows to 1e-9, so
  the offline demo is not a mock.
- **Guardrails as engineering.** Read-only screen, a table-function and table
  allowlist over comment-stripped SQL (a read-only `SELECT * FROM url('http://169.254.169.254/...')`
  is rejected before it can reach a cloud metadata endpoint), a per-run action
  limiter, and server-side bounds. Every decision is written to the run's audit
  trail, so the UI shows the real record.
- **A product, not a CLI.** A dependency-light stdlib server serves the UI and a
  JSON API, deployed to Cloud Run so a judge can use it on the first click. The UI
  turns amber and says "recorded transcript, not live" when opened as a file, so
  it never pretends to be live when it is not.

## Challenges we ran into

Making the MCP path genuinely load-bearing was the hard part: an earlier version
silently fell back to in-process tools while still reporting success. Now the MCP
transport fails loudly rather than downgrading, and `mcp-check` exists precisely so
the load-bearing call is checkable. Keeping the model from inventing numbers was
the other: the fix is architectural, the agent quotes only rows that returned and
abstains otherwise, which is also the differentiation.

## Accomplishments we are proud of

Gemini writes the SQL and calls ClickHouse's own MCP server, and the answer is
grounded in the returned rows. The agent refuses to invent a number. Offline, HTTP
and MCP transports are cell-for-cell identical. There is a full guardrail audit
trail and a live hosted demo. And there is an `HONESTY.md` that maps, line by line,
what is real and how to falsify each claim.

## What we learned

ClickHouse's own published stance is that trustworthy agents ground answers in
query results rather than hallucinating, and that correctness is judged by
result-set equivalence, not by how confident the model sounds. Building the whole
product around honest grounding turned out to align exactly with what the sponsor
says good looks like, and honest abstention is the one thing a generic text-to-SQL
demo never does.

## What's next

A private ClickHouse Cloud service in place of the public playground, a holdout
evaluation harness that measures answer quality over a question distribution,
richer query planning, and cohort-grounded audience signals for reaction questions.

## Built with

python, google-gemini, google-adk, vertex-ai, google-cloud, clickhouse,
model-context-protocol, mcp, sqlite

## How we used Google Cloud and ClickHouse (runtime evidence)

The rules require the code to import and call Google Cloud and the Partner service
at runtime, not just name them. We do both:

- Google Cloud: `google.adk` + `google-genai` on Vertex AI. Gemini plans and
  writes the SQL. Reproduce: `GOOGLE_GENAI_USE_VERTEXAI=True GOOGLE_CLOUD_PROJECT=<project> BOX_TRANSPORT=mcp boxoffice ask "which genres underperformed in 1999 versus 1998?"`. Captured: `docs/gemini-run.txt`.
- ClickHouse: the official `mcp-clickhouse` server, `run_query` tool. Reproduce:
  `boxoffice mcp-check`. Captured: `docs/live-proof.txt`.

## Try it / testing instructions for judges

```bash
pip install -e '.[mcp]'          # agent-core is vendored in-tree; no monorepo needed
boxoffice mcp-check              # prove the ClickHouse MCP run_query call is real
boxoffice ask "which genres underperformed in 1999 vs 1998?" --no-llm   # keyless, offline
BOX_TRANSPORT=mcp boxoffice ask "..." --no-llm                          # live ClickHouse, no key
boxoffice serve                  # the UI + JSON API on localhost
# the full Gemini path (your own Google Cloud project):
GOOGLE_GENAI_USE_VERTEXAI=True GOOGLE_CLOUD_PROJECT=<project> BOX_TRANSPORT=mcp boxoffice ask "..."
```

Tests: `BOX_IN_MEMORY_STATE=true pytest tests -q` (35 pass, keyless).

## Links

- Live demo: https://boxoffice-brain-744757588430.us-central1.run.app
- Repository: https://github.com/doom2quake/boxoffice (MIT)
- Video (3 min): VIDEO_URL
- What is real, and how to falsify it: `HONESTY.md`
