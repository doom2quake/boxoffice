"""BoxOffice Brain configuration.

Google Cloud (Gemini + ADK) is the mandatory platform for Agentic Cinema;
ClickHouse, reached through the official ClickHouse MCP server, is the
load-bearing partner integration.

Three transports, chosen explicitly, never silently:

  * ``mcp``     the official ClickHouse MCP server (``mcp-clickhouse``) over
                stdio. This is the judged path.
  * ``http``    ClickHouse's own HTTP interface, same SQL, no MCP hop. Kept so
                the MCP hop can be measured against a baseline.
  * ``offline`` a real SQLite engine over a committed snapshot of the same
                ClickHouse tables. Deterministic, no network, used by tests.

Defaults point at the public ClickHouse SQL playground
(``sql-clickhouse.clickhouse.com``, user ``demo``, no password), which is the
same endpoint the official ClickHouse MCP server ships as its default. That is
why this repo can prove a live warehouse call without a funded key.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agent_core import BaseSettings, env_bool, env_int, env_str

#: Transports that ``BOX_TRANSPORT`` accepts.
TRANSPORTS = ("offline", "http", "mcp")

#: Tables the agent is allowed to read. Anything else is refused before the
#: query leaves the process. Keep this narrow: it is the data-scope guardrail.
DEFAULT_ALLOWED_TABLES = (
    "imdb.movies,imdb.genres,imdb.actors,imdb.directors,"
    "imdb.movie_directors,imdb.roles,system.columns,system.tables"
)


@dataclass(frozen=True)
class BoxOfficeSettings(BaseSettings):
    env_prefix: str = "BOX"
    app_name: str = "boxoffice"

    # --- transport -----------------------------------------------------------
    transport: str = field(default_factory=lambda: env_str("BOX_TRANSPORT", "offline").strip().lower())

    # --- ClickHouse endpoint (defaults = the public ClickHouse SQL playground)
    clickhouse_host: str = field(default_factory=lambda: env_str("BOX_CLICKHOUSE_HOST", "sql-clickhouse.clickhouse.com"))
    clickhouse_port: int = field(default_factory=lambda: env_int("BOX_CLICKHOUSE_PORT", 8443))
    clickhouse_user: str = field(default_factory=lambda: env_str("BOX_CLICKHOUSE_USER", "demo"))
    clickhouse_password: str = field(default_factory=lambda: env_str("BOX_CLICKHOUSE_PASSWORD"))
    clickhouse_secure: bool = field(default_factory=lambda: env_bool("BOX_CLICKHOUSE_SECURE", True))
    clickhouse_database: str = field(default_factory=lambda: env_str("BOX_CLICKHOUSE_DATABASE", "imdb"))

    # --- official ClickHouse MCP server launcher ------------------------------
    # `uvx mcp-clickhouse` fetches and runs the ClickHouse-published server.
    mcp_command: str = field(default_factory=lambda: env_str("BOX_MCP_COMMAND", "uvx"))
    mcp_args: str = field(default_factory=lambda: env_str("BOX_MCP_ARGS", "--python,3.11,mcp-clickhouse"))
    mcp_startup_timeout_s: int = field(default_factory=lambda: env_int("BOX_MCP_STARTUP_TIMEOUT_S", 180))

    # --- hard query bounds (enforced server-side AND client-side) -------------
    max_rows: int = field(default_factory=lambda: env_int("BOX_MAX_ROWS", 200))
    max_result_bytes: int = field(default_factory=lambda: env_int("BOX_MAX_RESULT_BYTES", 4_000_000))
    max_execution_time_s: int = field(default_factory=lambda: env_int("BOX_MAX_EXECUTION_TIME_S", 20))
    http_timeout_s: int = field(default_factory=lambda: env_int("BOX_HTTP_TIMEOUT_S", 30))

    # --- data-scope guardrail -------------------------------------------------
    allowed_tables: str = field(default_factory=lambda: env_str("BOX_ALLOWED_TABLES", DEFAULT_ALLOWED_TABLES))

    def __post_init__(self) -> None:
        # BaseSettings.__post_init__ applies the `BOX_*` overrides (state backend,
        # models, collection). Skipping it silently disabled BOX_IN_MEMORY_STATE.
        super().__post_init__()
        if self.transport not in TRANSPORTS:
            raise ValueError(f"BOX_TRANSPORT must be one of {TRANSPORTS}, got {self.transport!r}")

    @property
    def allowed_table_set(self) -> frozenset[str]:
        return frozenset(t.strip().lower() for t in self.allowed_tables.split(",") if t.strip())

    @property
    def clickhouse_url(self) -> str:
        scheme = "https" if self.clickhouse_secure else "http"
        return f"{scheme}://{self.clickhouse_host}:{self.clickhouse_port}/"

    @property
    def is_offline(self) -> bool:
        return self.transport == "offline"


settings = BoxOfficeSettings()
