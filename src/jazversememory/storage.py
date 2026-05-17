from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def normalize_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        value = re.sub(r"\s+", "-", str(tag).strip().lower())
        if value and value not in seen:
            normalized.append(value)
            seen.add(value)
    return normalized


@dataclass(frozen=True)
class MemoryStore:
    db_path: Path

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    source TEXT,
                    importance INTEGER NOT NULL DEFAULT 3,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
                USING fts5(id UNINDEXED, content, tags);

                CREATE TABLE IF NOT EXISTS memory_links (
                    id TEXT PRIMARY KEY,
                    from_id TEXT NOT NULL,
                    to_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(from_id) REFERENCES memories(id) ON DELETE CASCADE,
                    FOREIGN KEY(to_id) REFERENCES memories(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_memory_links_from ON memory_links(from_id);
                CREATE INDEX IF NOT EXISTS idx_memory_links_to ON memory_links(to_id);
                """
            )

    def add_memory(
        self,
        content: str,
        tags: list[str] | None = None,
        source: str | None = None,
        importance: int = 3,
    ) -> dict[str, Any]:
        memory_id = f"mem_{uuid4().hex[:16]}"
        now = utc_now()
        clean_tags = normalize_tags(tags)
        importance = min(5, max(1, int(importance)))
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO memories (id, content, tags_json, source, importance, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (memory_id, content.strip(), json.dumps(clean_tags), source, importance, now, now),
            )
            conn.execute(
                "INSERT INTO memories_fts (id, content, tags) VALUES (?, ?, ?)",
                (memory_id, content.strip(), " ".join(clean_tags)),
            )
        return self.get_memory(memory_id) or {"id": memory_id}

    def get_memory(self, memory_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        return self._memory_from_row(row) if row else None

    def get_memories(self, ids: list[str]) -> list[dict[str, Any]]:
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        with self.connect() as conn:
            rows = conn.execute(f"SELECT * FROM memories WHERE id IN ({placeholders})", ids).fetchall()
        by_id = {row["id"]: self._memory_from_row(row) for row in rows}
        return [by_id[memory_id] for memory_id in ids if memory_id in by_id]

    def search_memories(
        self,
        query: str,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        clean_tags = normalize_tags(tags)
        limit = min(50, max(1, int(limit)))
        seen_ids: set[str] = set()
        candidate_rows: list[sqlite3.Row] = []
        with self.connect() as conn:
            if query.strip():
                rows = conn.execute(
                    """
                    SELECT m.*, bm25(memories_fts) AS score
                    FROM memories_fts
                    JOIN memories m ON m.id = memories_fts.id
                    WHERE memories_fts MATCH ?
                    ORDER BY score, m.importance DESC, m.updated_at DESC
                    LIMIT ?
                    """,
                    (self._fts_query(query), limit * 3),
                ).fetchall()
                candidate_rows.extend(rows)
                seen_ids.update(row["id"] for row in rows)

                fallback_rows = conn.execute(
                    "SELECT *, 0.0 AS score FROM memories ORDER BY importance DESC, updated_at DESC"
                ).fetchall()
                for row in fallback_rows:
                    if row["id"] not in seen_ids and self._loose_match(query, row["content"], row["tags_json"]):
                        candidate_rows.append(row)
                        seen_ids.add(row["id"])
            else:
                candidate_rows = conn.execute(
                    "SELECT *, 0.0 AS score FROM memories ORDER BY importance DESC, updated_at DESC LIMIT ?",
                    (limit * 3,),
                ).fetchall()

        results = []
        for row in candidate_rows:
            memory = self._memory_from_row(row)
            if clean_tags and not all(tag in memory["tags"] for tag in clean_tags):
                continue
            if "score" in row.keys():
                memory["score"] = row["score"]
            results.append(memory)
            if len(results) >= limit:
                break
        return results

    def update_memory(
        self,
        memory_id: str,
        content: str | None = None,
        tags: list[str] | None = None,
        source: str | None = None,
        importance: int | None = None,
    ) -> dict[str, Any] | None:
        current = self.get_memory(memory_id)
        if not current:
            return None

        new_content = content.strip() if content is not None else current["content"]
        new_tags = normalize_tags(tags) if tags is not None else current["tags"]
        new_source = source if source is not None else current["source"]
        new_importance = min(5, max(1, int(importance))) if importance is not None else current["importance"]
        now = utc_now()

        with self.connect() as conn:
            conn.execute(
                """
                UPDATE memories
                SET content = ?, tags_json = ?, source = ?, importance = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_content, json.dumps(new_tags), new_source, new_importance, now, memory_id),
            )
            conn.execute("DELETE FROM memories_fts WHERE id = ?", (memory_id,))
            conn.execute(
                "INSERT INTO memories_fts (id, content, tags) VALUES (?, ?, ?)",
                (memory_id, new_content, " ".join(new_tags)),
            )
        return self.get_memory(memory_id)

    def delete_memories(self, ids: list[str] | None = None, tags: list[str] | None = None) -> dict[str, Any]:
        clean_tags = normalize_tags(tags)
        deleted: list[str] = []
        with self.connect() as conn:
            if ids:
                for memory_id in ids:
                    if conn.execute("SELECT 1 FROM memories WHERE id = ?", (memory_id,)).fetchone():
                        conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
                        conn.execute("DELETE FROM memories_fts WHERE id = ?", (memory_id,))
                        deleted.append(memory_id)
            elif clean_tags:
                rows = conn.execute("SELECT id, tags_json FROM memories").fetchall()
                for row in rows:
                    row_tags = json.loads(row["tags_json"])
                    if all(tag in row_tags for tag in clean_tags):
                        conn.execute("DELETE FROM memories WHERE id = ?", (row["id"],))
                        conn.execute("DELETE FROM memories_fts WHERE id = ?", (row["id"],))
                        deleted.append(row["id"])
        return {"deleted_count": len(deleted), "deleted_ids": deleted}

    def link_memories(self, from_id: str, to_id: str, relation: str) -> dict[str, Any]:
        link_id = f"link_{uuid4().hex[:16]}"
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_links (id, from_id, to_id, relation, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (link_id, from_id, to_id, relation.strip() or "related_to", now),
            )
        return {"id": link_id, "from_id": from_id, "to_id": to_id, "relation": relation, "created_at": now}

    def get_memory_neighborhood(self, memory_id: str, depth: int = 1, limit: int = 25) -> dict[str, Any]:
        depth = min(3, max(1, int(depth)))
        limit = min(100, max(1, int(limit)))
        seen = {memory_id}
        frontier = {memory_id}
        links: list[dict[str, Any]] = []

        with self.connect() as conn:
            for _ in range(depth):
                if not frontier or len(seen) >= limit:
                    break
                placeholders = ",".join("?" for _ in frontier)
                rows = conn.execute(
                    f"""
                    SELECT * FROM memory_links
                    WHERE from_id IN ({placeholders}) OR to_id IN ({placeholders})
                    """,
                    list(frontier) + list(frontier),
                ).fetchall()
                next_frontier: set[str] = set()
                for row in rows:
                    link = dict(row)
                    links.append(link)
                    for node_id in (row["from_id"], row["to_id"]):
                        if node_id not in seen and len(seen) < limit:
                            seen.add(node_id)
                            next_frontier.add(node_id)
                frontier = next_frontier

        return {"memories": self.get_memories(list(seen)), "links": links}

    def get_graph_hubs(self, limit: int = 15) -> list[dict[str, Any]]:
        limit = min(50, max(1, int(limit)))
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT m.*, COUNT(l.id) AS degree
                FROM memories m
                LEFT JOIN memory_links l ON l.from_id = m.id OR l.to_id = m.id
                GROUP BY m.id
                ORDER BY degree DESC, m.importance DESC, m.updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        hubs = []
        for row in rows:
            memory = self._memory_from_row(row)
            memory["degree"] = row["degree"]
            hubs.append(memory)
        return hubs

    def get_stats(self) -> dict[str, Any]:
        with self.connect() as conn:
            memories = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            links = conn.execute("SELECT COUNT(*) FROM memory_links").fetchone()[0]
            tags_rows = conn.execute("SELECT tags_json FROM memories").fetchall()
        tag_counts: dict[str, int] = {}
        for row in tags_rows:
            for tag in json.loads(row["tags_json"]):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        return {"memory_count": memories, "link_count": links, "tags": tag_counts}

    @staticmethod
    def _memory_from_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "content": row["content"],
            "tags": json.loads(row["tags_json"]),
            "source": row["source"],
            "importance": row["importance"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _fts_query(query: str) -> str:
        terms = re.findall(r"[A-Za-z0-9_@./:-]+", query)
        if not terms:
            return '""'
        return " OR ".join(f'"{term}"' for term in terms[:20])

    @staticmethod
    def _loose_match(query: str, content: str, tags_json: str) -> bool:
        haystack = f"{content} {' '.join(json.loads(tags_json))}".lower()
        terms = [term.lower() for term in re.findall(r"[A-Za-z0-9_@./:-]+", query)]
        for term in terms:
            if len(term) < 4:
                continue
            roots = {term, re.sub(r"(ing|ed|es|s)$", "", term)}
            if any(root and root in haystack for root in roots):
                return True
        return False
