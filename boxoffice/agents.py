"""BoxOffice Brain agent graph — a Gemini/ADK supervisor over the analytics skills.

Assembled with agent-core's `build_supervisor` (ADK-native; agent-core is helper
code on top of google.adk, the Agentic Cinema-mandated stack).

How the official ClickHouse MCP server is wired, and why:

  * DEFAULT — the Analyst's tool is our `run_clickhouse_sql`, and with
    `BOX_TRANSPORT=mcp` that tool executes through ClickHouse's own MCP server.
    The official server does the work; our read-only, data-scope and rate
    guardrails sit in front of it. Guarded by construction.

  * `BOX_MCP_TOOLSET=true` — hand ADK the official server's own tools
    (`run_query`, `list_databases`, `list_tables`) directly. This is the
    ADK-native MCP wiring, and it is honestly weaker: the model then talks to
    the server with no scope guardrail of ours in between. Offered for
    comparison, not shipped as the default, and it FAILS CLOSED: if the server
    cannot start, importing this module raises instead of quietly falling back
    to in-process tools.
"""

from __future__ import annotations

import os

from agent_core import agent_from_skill, build_supervisor

from .skills import GROUND_ANSWER, PLAN_ANALYSIS, RUN_ANALYSIS


def _use_raw_toolset() -> bool:
    return os.getenv("BOX_MCP_TOOLSET", "").strip().lower() in {"1", "true", "yes", "on"}


def _analyst_tools():
    """Return the Analyst's tools. Raises if the requested MCP wiring is broken."""
    if not _use_raw_toolset():
        return list(RUN_ANALYSIS.tools)
    from .mcp_clickhouse import official_mcp_toolset  # fails closed by raising

    return [official_mcp_toolset()]


_analyst = agent_from_skill(RUN_ANALYSIS, tools=_analyst_tools())

root_agent = build_supervisor(
    name="boxoffice_supervisor",
    description=(
        "BoxOffice Brain - a cinema-catalogue analytics agent that reasons over a "
        "ClickHouse film warehouse: plans an analysis, runs grounded read-only SQL "
        "through the official ClickHouse MCP server, and answers (or abstains) "
        "with the evidence trace."
    ),
    instruction=(
        "You are BoxOffice Brain, an analytics agent for a film studio's "
        "distribution team. Answer the user's question by delegating IN ORDER:\n"
        "  1. Transfer to `plan_analysis_agent` to inspect the schema and plan.\n"
        "  2. Transfer to `run_analysis_agent` to run grounded ClickHouse SQL.\n"
        "  3. Transfer to `ground_answer_agent` to write the grounded answer or "
        "abstain if the data cannot support one.\n"
        "A tool result with a status other than `ok` is a FAILURE, not an empty "
        "dataset: report it as a failure and do not describe it as a finding. "
        "Keep the user informed at each step. Your final message is the grounded "
        "answer with its evidence trace. Never invent numbers not in the rows."
    ),
    skills=[PLAN_ANALYSIS, RUN_ANALYSIS, GROUND_ANSWER],
    sub_agents=[agent_from_skill(PLAN_ANALYSIS), _analyst, agent_from_skill(GROUND_ANSWER)],
)
