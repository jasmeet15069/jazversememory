from pathlib import Path

from jazversememory.storage import MemoryStore


def test_add_search_link_and_stats(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.initialize()

    first = store.add_memory(
        "User wants JazverseMemory deployed as a persistent MCP memory server.",
        tags=["jazverse", "mcp"],
    )
    second = store.add_memory(
        "Deployment target is ssh root@45.79.124.28.",
        tags=["jazverse", "deployment"],
        importance=5,
    )
    link = store.link_memories(first["id"], second["id"], "deploys_to")

    results = store.search_memories("Where should JazverseMemory deploy?", limit=5)
    assert {item["id"] for item in results} >= {first["id"], second["id"]}
    assert link["relation"] == "deploys_to"

    neighborhood = store.get_memory_neighborhood(first["id"])
    assert len(neighborhood["links"]) == 1

    stats = store.get_stats()
    assert stats["memory_count"] == 2
    assert stats["link_count"] == 1
