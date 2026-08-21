"""BoxOffice Brain skills — a cinema-catalogue analytics workflow.

Plan -> query ClickHouse -> ground the answer (or abstain). The abstain step is
deliberate: the ClickHouse track rewards an agent that grounds every claim in
rows it actually retrieved and refuses to answer when the data cannot support
it, rather than hallucinating a plausible number.
"""

from __future__ import annotations

from agent_core import Skill

from .config import settings
from .clickhouse_tools import describe_tables, run_clickhouse_sql

# --- 1) plan the analysis ----------------------------------------------------

PLAN_ANALYSIS = Skill(
    name="plan-analysis",
    summary=(
        "Turns a studio catalogue question into a concrete analytical plan "
        "(which tables, metrics, dimensions, and comparison). Use first."
    ),
    model=settings.model_fast,
    instruction=(
        "You are BoxOffice Brain's Planner, an analyst for a film studio. Call "
        "`describe_tables` to see the ClickHouse film warehouse schema; it lists "
        "every table you are permitted to read. Given the user's question (e.g. "
        "'which genres underperformed in 1999 versus 1998?'), state a short plan: "
        "the metric(s), the comparison (this year vs prior year), the dimensions "
        "to slice by (genre, title), and any second signal to check (the "
        "lowest-rated titles inside the worst genre and year). If the schema does "
        "not contain what the question needs, say so plainly instead of inventing "
        "a table. Do not write SQL yet."
    ),
    tools=[describe_tables],
    output_key="analysis_plan",
)

# --- 2) run the analysis (ClickHouse SQL = the load-bearing step) ------------

RUN_ANALYSIS = Skill(
    name="run-analysis",
    summary=(
        "Writes and runs READ-ONLY ClickHouse SQL to answer the plan, returning "
        "rows plus a grounding trace. Use after planning."
    ),
    model=settings.model_fast,
    instruction=(
        "You are BoxOffice Brain's Analyst. Execute the analysis_plan by writing "
        "READ-ONLY ClickHouse SQL and running it with `run_clickhouse_sql` (pass a "
        "short `note` describing each query's purpose). Rules the tool enforces, so "
        "write to them: a single SELECT/WITH statement; only the tables "
        "`describe_tables` listed; no table functions such as url(), file(), s3() "
        "or remote(); no SETTINGS clause. Iterate: compute the metric, compare it "
        "against the prior-year baseline, rank the under-performers, then pull the "
        "detail signal FOR THE SPECIFIC genre and year the ranking named, never a "
        "global one. Check `status` on every result: only `ok` carries rows; "
        "`rejected`, `suppressed` and `error` mean the query did not run and must "
        "be reported as a failure, not as an empty dataset. Report the concrete "
        "rows AND the grounding trace (sql, rows_read, elapsed_ms) for each query. "
        "Do not interpret yet, just gather grounded rows."
    ),
    tools=[run_clickhouse_sql],
    output_key="analysis_rows",
)

# --- 3) ground the answer or abstain -----------------------------------------

GROUND_ANSWER = Skill(
    name="ground-answer",
    summary=(
        "Synthesises a grounded, decision-ready answer from the retrieved rows, "
        "or abstains if the data does not support one. Use last."
    ),
    model=settings.model_deep,
    instruction=(
        "You are BoxOffice Brain's Answer Writer for a distribution exec. Using "
        "ONLY the analysis_rows in session state, write a concise, decision-ready "
        "answer: which genres or titles under- or over-performed, by how much (cite "
        "the actual numbers), and the detail signal from the same cohort. Describe "
        "that signal as an association within the cohort, never as a proven cause. "
        "EVERY quantitative claim must trace to a retrieved row. If the rows do not "
        "contain comparable data for the question (empty result, no baseline, wrong "
        "grain), or if a query failed, you MUST ABSTAIN: say plainly 'Insufficient "
        "comparable data to answer' and state exactly what data would be needed. Do "
        "not estimate or fill gaps from general knowledge. End with the grounding "
        "trace (queries run + rows) so the answer is auditable."
    ),
    tools=[],
    output_key="grounded_answer",
)

CATALOGUE = [PLAN_ANALYSIS, RUN_ANALYSIS, GROUND_ANSWER]
