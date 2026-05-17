# JazverseMemory MCP

`jazversememory` is a local/remote MCP server for persistent user and project context memory. It stores durable facts in SQLite, supports full-text search, links related memories, and exposes memory tools over MCP streamable HTTP at `/mcp`.

## Tools

- `add_memory` - store one durable fact, preference, decision, credential location, project note, or relationship.
- `search_memories` - search stored memories using natural-language text and optional tag filters.
- `get_memories` - fetch memories by id.
- `update_memory` - revise an existing memory.
- `delete_memories` - delete memories by id or tag.
- `link_memories` - create a relationship between two memories.
- `get_memory_neighborhood` - inspect linked memories around one memory.
- `get_graph_hubs` - list the most connected memories.
- `get_stats` - show storage totals.

## Local Run

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -e .
$env:JAZVERSE_MEMORY_DB="data/jazversememory.sqlite3"
.\.venv\Scripts\jazversememory --host 127.0.0.1 --port 8787
```

MCP URL:

```text
http://127.0.0.1:8787/mcp
```

## Deploy Target

Target server:

```text
ssh root@45.79.124.28
```

The production service is intended to run on port `8787` behind a reverse proxy such as Caddy or Nginx.

## Codex Config

```powershell
codex mcp add jazversememory --url http://45.79.124.28:8787/mcp
```

If you add HTTPS later:

```powershell
codex mcp add jazversememory --url https://your-domain.example/mcp
```

## ChatGPT Custom MCP

Use:

```text
Name: JazverseMemory
MCP Server URL: https://your-domain.example/mcp
Authentication: No authentication
```

For public internet use, put it behind HTTPS and add authentication before storing sensitive data.
