"""Run edgar-mcp.

    uv run python -m finsight.mcp_edgar          # stdio: an agent starts it as a child process
    uv run python -m finsight.mcp_edgar --http   # streamable HTTP on http://127.0.0.1:8000/mcp

Same tools either way; only the connection changes (book 12.2).
"""

import sys

from finsight.mcp_edgar.server import mcp

mcp.run("streamable-http" if "--http" in sys.argv else "stdio")
