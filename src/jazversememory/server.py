from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .storage import MemoryStore


DEFAULT_DB_PATH = Path(os.getenv("JAZVERSE_MEMORY_DB", "data/jazversememory.sqlite3"))

store = MemoryStore(DEFAULT_DB_PATH)
store.initialize()

mcp = FastMCP(
    name="jazversememory",
    instructions=(
        "JazverseMemory is persistent context memory for the user and their projects. "
        "Store durable facts atomically, preserve exact names/numbers/URLs/paths, "
        "search before answering user-specific questions, and do not store secrets."
    ),
    host=os.getenv("JAZVERSE_MEMORY_HOST", "127.0.0.1"),
    port=int(os.getenv("JAZVERSE_MEMORY_PORT", "8787")),
    streamable_http_path="/mcp",
)


@mcp.tool()
def add_memory(
    content: str,
    tags: list[str] | None = None,
    source: str | None = None,
    importance: int = 3,
) -> dict[str, Any]:
    """Store one durable, atomic memory with optional tags and importance from 1 to 5."""
    return store.add_memory(content=content, tags=tags, source=source, importance=importance)


@mcp.tool()
def search_memories(query: str, tags: list[str] | None = None, limit: int = 10) -> list[dict[str, Any]]:
    """Search persistent memories. Use full-sentence queries and optional tag filters."""
    return store.search_memories(query=query, tags=tags, limit=limit)


@mcp.tool()
def get_memories(ids: list[str]) -> list[dict[str, Any]]:
    """Fetch full memory records by id."""
    return store.get_memories(ids)


@mcp.tool()
def update_memory(
    memory_id: str,
    content: str | None = None,
    tags: list[str] | None = None,
    source: str | None = None,
    importance: int | None = None,
) -> dict[str, Any] | None:
    """Update an existing memory. Unspecified fields are preserved."""
    return store.update_memory(
        memory_id=memory_id,
        content=content,
        tags=tags,
        source=source,
        importance=importance,
    )


@mcp.tool()
def delete_memories(ids: list[str] | None = None, tags: list[str] | None = None) -> dict[str, Any]:
    """Delete memories by explicit ids, or by tags when ids are omitted."""
    return store.delete_memories(ids=ids, tags=tags)


@mcp.tool()
def link_memories(from_id: str, to_id: str, relation: str = "related_to") -> dict[str, Any]:
    """Create a graph relationship between two memories."""
    return store.link_memories(from_id=from_id, to_id=to_id, relation=relation)


@mcp.tool()
def get_memory_neighborhood(memory_id: str, depth: int = 1, limit: int = 25) -> dict[str, Any]:
    """Return linked memories around one memory id."""
    return store.get_memory_neighborhood(memory_id=memory_id, depth=depth, limit=limit)


@mcp.tool()
def get_graph_hubs(limit: int = 15) -> list[dict[str, Any]]:
    """Return the most connected memories in the graph."""
    return store.get_graph_hubs(limit=limit)


@mcp.tool()
def get_stats() -> dict[str, Any]:
    """Return memory database totals and tag counts."""
    return store.get_stats()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the JazverseMemory MCP server.")
    parser.add_argument("--host", default=os.getenv("JAZVERSE_MEMORY_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("JAZVERSE_MEMORY_PORT", "8787")))
    parser.add_argument("--db", default=os.getenv("JAZVERSE_MEMORY_DB", str(DEFAULT_DB_PATH)))
    args = parser.parse_args()

    global store
    store = MemoryStore(Path(args.db))
    store.initialize()
    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
