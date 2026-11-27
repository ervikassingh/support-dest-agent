"""Hybrid search: BM25 and cosine distance, fused with reciprocal rank fusion."""

from __future__ import annotations

import re
from typing import Any

from pgvector.psycopg.vector import Vector
from psycopg import sql

from rag.db import active_chunk_table, connection
from rag.embed import embed_texts
from rag.settings import get_settings

_COLUMNS = """
id::text AS id,
document_id::text AS document_id,
version, content_hash, source_type, source_uri, title, header_path,
page_start, page_end, chunk_index, char_start, char_end,
embedding_model, content, embed_text
"""


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))


def bm25_query_text(query: str) -> str:
    cleaned = re.sub(r"[^\w\s.-]", " ", query, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or "document"


def canonicalize(rows: list[dict[str, Any]], rankings: list[list[str]]) -> list[list[str]]:
    """Point every version of the same text at the newest row, then drop duplicates."""
    newest: dict[str, dict[str, Any]] = {}
    for row in rows:
        current = newest.get(row["content_hash"])
        if current is None or row["version"] > current["version"]:
            newest[row["content_hash"]] = row
    alias = {row["id"]: newest[row["content_hash"]]["id"] for row in rows}
    rewritten: list[list[str]] = []
    for ranking in rankings:
        seen: set[str] = set()
        cleaned: list[str] = []
        for item in ranking:
            canonical = alias.get(item, item)
            if canonical in seen:
                continue
            seen.add(canonical)
            cleaned.append(canonical)
        rewritten.append(cleaned)
    return rewritten


async def _bm25(conn, table: str, query: str, limit: int) -> list[str]:
    statement = sql.SQL(
        """
        SELECT id::text AS id
        FROM {}
        WHERE embed_text ||| %s
        ORDER BY pdb.score(id) DESC, id
        LIMIT %s
        """
    ).format(sql.Identifier(table))
    result = await conn.execute(statement, (bm25_query_text(query), limit))
    return [row["id"] async for row in result]


async def _vector(conn, table: str, vector: list[float], limit: int) -> list[str]:
    statement = sql.SQL(
        """
        SELECT id::text AS id
        FROM {}
        ORDER BY embedding <=> %s
        LIMIT %s
        """
    ).format(sql.Identifier(table))
    result = await conn.execute(statement, (Vector(vector), limit))
    return [row["id"] async for row in result]


async def _fetch(conn, table: str, ids: list[str]) -> list[dict[str, Any]]:
    if not ids:
        return []
    statement = sql.SQL("SELECT {} FROM {} WHERE id = ANY(%s)").format(
        sql.SQL(_COLUMNS),
        sql.Identifier(table),
    )
    result = await conn.execute(statement, (ids,))
    return [dict(row) async for row in result]


def _citation(index: int, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "n": index,
        "document_id": row["document_id"],
        "title": row["title"],
        "header_path": row["header_path"],
        "page_start": row["page_start"],
        "page_end": row["page_end"],
        "version": row["version"],
        "source_uri": row["source_uri"],
        "source_type": row["source_type"],
    }


async def retrieve(query: str, top_k: int = 5) -> dict[str, Any]:
    settings = get_settings()
    table = active_chunk_table()
    vectors, usage = await embed_texts([query])
    async with connection() as conn:
        exists = await conn.execute("SELECT to_regclass(%s) AS name", (table,))
        if (await exists.fetchone())["name"] is None:
            return {
                "query": query,
                "documents": [],
                "citations": [],
                "usage": usage,
                "note": f"No index for {settings.embedding_model} ({settings.embedding_dim}).",
            }
        lexical = await _bm25(conn, table, query, settings.candidate_k)
        semantic = await _vector(conn, table, vectors[0], settings.candidate_k)
        rows = await _fetch(conn, table, list(dict.fromkeys([*lexical, *semantic])))

    by_id = {row["id"]: row for row in rows}
    fused = reciprocal_rank_fusion(
        canonicalize(rows, [lexical, semantic]),
        k=settings.rrf_k,
    )
    documents = []
    citations = []
    for item_id, score in fused[:top_k]:
        row = dict(by_id[item_id])
        row["score"] = score
        documents.append(row)
        citations.append(_citation(len(citations) + 1, row))
    return {"query": query, "documents": documents, "citations": citations, "usage": usage}
