"""BoxOffice Brain — a grounded cinema-analytics agent built on agent-core.

Google Cloud (Gemini + ADK) is the mandated platform; ClickHouse, reached
through ClickHouse's own published MCP server (`mcp-clickhouse`), is the
load-bearing analytical backbone. Built for the Agentic Cinema Blockbuster
Hackathon 2026, ClickHouse track.

See HONESTY.md for what is demonstrated and what is not.
"""

from .config import settings

__all__ = ["settings"]
__version__ = "0.1.0"
