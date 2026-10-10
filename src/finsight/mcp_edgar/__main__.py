"""Run: uv run python -m finsight.mcp_edgar   (stdio, for a local agent)."""

from finsight.mcp_edgar.server import mcp

mcp.run()  # stdio by default
