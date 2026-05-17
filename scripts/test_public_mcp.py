import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


URL = "https://imperceptibly-hymnlike-leesa.ngrok-free.dev/mcp"


async def main() -> None:
    async with streamablehttp_client(URL) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f"connected={URL}")
            print(f"tool_count={len(tools.tools)}")
            for tool in sorted(tools.tools, key=lambda item: item.name):
                print(tool.name)

            added = await session.call_tool(
                "add_memory",
                {
                    "content": "Connectivity smoke test for JazverseMemory public MCP tunnel.",
                    "tags": ["smoke-test", "jazversememory"],
                    "source": "scripts/test_public_mcp.py",
                    "importance": 1,
                },
            )
            memory = added.structuredContent or {}
            if "id" not in memory:
                raise RuntimeError(f"Unexpected add_memory result: {added!r}")
            memory_id = memory["id"]
            found = await session.call_tool(
                "search_memories",
                {"query": "Connectivity smoke test for public MCP tunnel", "tags": ["smoke-test"], "limit": 5},
            )
            found_payload = found.structuredContent or []
            memories = found_payload.get("result", found_payload) if isinstance(found_payload, dict) else found_payload
            if not isinstance(memories, list):
                raise RuntimeError(f"Unexpected search_memories result: {found!r}")
            matched_ids = [item["id"] for item in memories]
            cleanup_ids = sorted(set(matched_ids + [memory_id]))
            await session.call_tool("delete_memories", {"ids": cleanup_ids})
            print(f"round_trip_memory_id={memory_id}")
            print(f"round_trip_found={memory_id in matched_ids}")


if __name__ == "__main__":
    asyncio.run(main())
