"""ParadeDB connection, document rows, and per-model chunk tables."""

from __future__ import annotations

import hashlib
import re
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from pgvector.psycopg import register_vector_async
from psycopg import AsyncConnection, sql
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from rag.settings import get_settings

_pool: AsyncConnectionPool | None = None

_DOCUMENT_TABLE = """
CREATE TABLE IF NOT EXISTS documents (
    id uuid PRIMARY KEY,
    source_key text NOT NULL,
    version int NOT NULL,
    filename text NOT NULL,
    source_type text,
    source_uri text,
    title text,
    content_hash text,
    status text NOT NULL,
    error text,
    storage_path text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_key, version)
)
"""


def chunk_table(model: str, dim: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", model.lower()).strip("_") or "model"
    name = f"chunks_{slug}_{dim}"
    if len(name) <= 50:
        return name
    digest = hashlib.sha1(name.encode()).hexdigest()[:8]
    return f"chunks_{digest}_{dim}"


def active_chunk_table() -> str:
    settings = get_settings()
    return chunk_table(settings.embedding_model, settings.embedding_dim)


async def open_pool() -> None:
    global _pool
    if _pool is not None:
        return
    settings = get_settings()
    _pool = AsyncConnectionPool(
        conninfo=settings.database_url,
        min_size=1,
        max_size=8,
        kwargs={"row_factory": dict_row},
        open=False,
    )
    await _pool.open()


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def connection() -> AsyncIterator[AsyncConnection]:
    if _pool is None:
        await open_pool()
    assert _pool is not None
    async with _pool.connection() as conn:
        await register_vector_async(conn)
        yield conn


async def ensure_schema() -> None:
    if _pool is None:
        await open_pool()
    assert _pool is not None
    async with _pool.connection() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_search")
        await conn.execute(_DOCUMENT_TABLE)
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS documents_source_key_idx ON documents (source_key)"
        )
        await conn.commit()
        await register_vector_async(conn)
        await ensure_chunk_table(conn, active_chunk_table(), get_settings().embedding_dim)


def _vector_ddl(table: str, dim: int) -> sql.Composed:
    if not isinstance(dim, int) or not 1 <= dim <= 4096:
        raise ValueError(f"EMBEDDING_DIM must be an integer from 1 to 4096, got {dim}")
    return sql.SQL(
        """
        CREATE TABLE IF NOT EXISTS {} (
            id uuid PRIMARY KEY,
            document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            version int NOT NULL,
            content_hash text NOT NULL,
            source_type text,
            source_uri text,
            title text,
            header_path text,
            page_start int,
            page_end int,
            chunk_index int,
            char_start int,
            char_end int,
            embedding_model text NOT NULL,
            ingested_at timestamptz NOT NULL DEFAULT now(),
            content text NOT NULL,
            embed_text text NOT NULL,
            embedding vector({}) NOT NULL
        )
        """
    ).format(sql.Identifier(table), sql.SQL(str(dim)))


async def ensure_chunk_table(conn: AsyncConnection, table: str, dim: int) -> None:
    async with conn.transaction():
        await conn.execute(_vector_ddl(table, dim))
    await _create_bm25_index(conn, table)
    async with conn.transaction():
        await conn.execute(
            sql.SQL(
                "CREATE INDEX IF NOT EXISTS {} ON {} USING hnsw (embedding vector_cosine_ops)"
            ).format(sql.Identifier(f"{table}_vec"), sql.Identifier(table))
        )


async def _create_bm25_index(conn: AsyncConnection, table: str) -> None:
    name = sql.Identifier(f"{table}_bm25")
    target = sql.Identifier(table)
    statements = (
        sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} USING paradedb (id, embed_text)").format(
            name, target
        ),
        sql.SQL(
            "CREATE INDEX IF NOT EXISTS {} ON {} USING bm25 (id, embed_text) WITH (key_field = 'id')"
        ).format(name, target),
    )
    last_error: Exception | None = None
    for statement in statements:
        try:
            async with conn.transaction():
                await conn.execute(statement)
            return
        except Exception as exc:  # older ParadeDB builds still use USING bm25
            last_error = exc
    if last_error is not None:
        raise last_error


async def ping() -> bool:
    try:
        async with connection() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception:
        return False


def _row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    out = dict(row)
    for key in ("id", "document_id"):
        if key in out and out[key] is not None:
            out[key] = str(out[key])
    for key in ("created_at", "updated_at", "ingested_at"):
        if key in out and out[key] is not None:
            out[key] = out[key].isoformat()
    return out
