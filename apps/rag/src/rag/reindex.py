"""Re-embed stored chunks into the table for the current model and dimension."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from pgvector.psycopg.vector import Vector
from psycopg import sql

from rag.db import active_chunk_table, connection, ensure_chunk_table, ensure_schema
from rag.embed import embed_texts
from rag.settings import get_settings


async def reindex() -> dict[str, Any]:
    await ensure_schema()
    settings = get_settings()
    target = active_chunk_table()
    async with connection() as conn:
        found = await conn.execute(
            """
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public' AND tablename LIKE 'chunks_%'
            ORDER BY tablename
            """
        )
        names = [row["tablename"] async for row in found]
    source = target if target in names else next((name for name in names if name != target), None)
    if source is None and target not in names:
        return {"table": target, "copied": 0, "note": "Nothing to reindex. Ingest documents first."}
    source = source or target

    async with connection() as conn:
        result = await conn.execute(
            sql.SQL(
                """
                SELECT document_id::text AS document_id, version, content_hash, source_type,
                       source_uri, title, header_path, page_start, page_end, chunk_index,
                       char_start, char_end, content, embed_text
                FROM {}
                ORDER BY document_id, chunk_index
                """
            ).format(sql.Identifier(source))
        )
        records = [dict(row) async for row in result]

    vectors: list[list[float]] = []
    for start in range(0, len(records), 64):
        batch = records[start : start + 64]
        embedded, _usage = await embed_texts([row["embed_text"] for row in batch])
        vectors.extend(embedded)

    async with connection() as conn:
        await ensure_chunk_table(conn, target, settings.embedding_dim)
        async with conn.transaction():
            await conn.execute(sql.SQL("DELETE FROM {}").format(sql.Identifier(target)))
            for row, vector in zip(records, vectors, strict=True):
                await conn.execute(
                    sql.SQL(
                        """
                        INSERT INTO {} (
                            id, document_id, version, content_hash, source_type, source_uri,
                            title, header_path, page_start, page_end, chunk_index,
                            char_start, char_end, embedding_model, content, embed_text, embedding
                        )
                        VALUES (
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s
                        )
                        """
                    ).format(sql.Identifier(target)),
                    (
                        uuid.uuid4(),
                        row["document_id"],
                        row["version"],
                        row["content_hash"],
                        row["source_type"],
                        row["source_uri"],
                        row["title"],
                        row["header_path"],
                        row["page_start"],
                        row["page_end"],
                        row["chunk_index"],
                        row["char_start"],
                        row["char_end"],
                        settings.embedding_model,
                        row["content"],
                        row["embed_text"],
                        Vector(vector),
                    ),
                )
    return {"table": target, "source": source, "copied": len(records)}


def main() -> None:
    print(asyncio.run(reindex()))
