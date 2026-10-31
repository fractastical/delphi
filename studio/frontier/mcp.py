"""Official SDK 1.27.0 read-only MCP interface over the persistent store."""
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .models import Ref
from .store import Store


READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)


def make_mcp(store: Store):
    server = FastMCP("Delphi Frontier persistent read API", log_level="ERROR", instructions=(
        "Bounded reads from the same PostgreSQL store as HTTP. Exact versions, source assertions and "
        "node-local review status remain separate. No job execution, network fetch, publication or write tools."))

    @server.tool(annotations=READ)
    def frontier_search(query: str = "", kind: str | None = None, status: str | None = None,
                        limit: int = 20, after: str = "") -> dict:
        """Read public current versions using literal text and structured filters, maximum 50."""
        return store.search(query=query, kind=kind, status=status, limit=limit, after=after)

    @server.tool(annotations=READ)
    def frontier_get(target: Ref) -> dict:
        """Retrieve one exact public version and its separate node-local review status."""
        return store.get(target.model_dump())

    @server.tool(annotations=READ)
    def frontier_neighborhood(target: Ref, limit: int = 20) -> dict:
        """Read up to 50 typed edges at depth one, including review/dispute relationships."""
        return store.neighborhood(target.model_dump(), limit=limit)

    @server.tool(annotations=READ)
    def frontier_events(after: int = 0, limit: int = 20) -> dict:
        """Read an append-only public event page; consumers deduplicate event versions."""
        return store.events(after=after, limit=limit)

    return server
