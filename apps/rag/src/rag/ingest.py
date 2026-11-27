"""Reserve a document row, then parse, chunk, embed, and store it."""

from __future__ import annotations

import hashlib
import ipaddress
import re
import socket
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
from pgvector.psycopg.vector import Vector
from psycopg import sql
from psycopg.errors import UniqueViolation

from rag.chunking import chunk_markdown, document_title, embed_prefix
from rag.db import active_chunk_table, connection, ensure_chunk_table
from rag.detect import detect, google_export_url, suffix_for
from rag.embed import embed_texts
from rag.parse import parse_file
from rag.settings import get_settings

_MAX_BYTES = 20 * 1024 * 1024


def safe_filename(name: str) -> str:
    base = Path(name.replace("\\", "/")).name
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base).strip("._")
    return (base or "upload")[:120]


def assert_public_http_url(url: str) -> None:
    """Refuse non-http schemes and any host that resolves to a non-public address.

    shortcut: the address is checked before the connection, not pinned to it.
    """
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RuntimeError("Only public http(s) URLs can be ingested")
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as exc:
        raise RuntimeError(f"Could not resolve {parsed.hostname}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise RuntimeError(f"Refusing to fetch non-public address for {parsed.hostname}")


def slugify(source_key: str) -> str:
    name = re.sub(r"^https?://", "", source_key)
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", name).strip("-")[:80]
    return slug or "document"


def _public(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["id"] = str(out["id"])
    for key in ("created_at", "updated_at"):
        if out.get(key) is not None:
            out[key] = out[key].isoformat()
    return out


async def reserve_document(
    *,
    source_key: str,
    filename: str,
    source_uri: str | None,
) -> dict[str, Any]:
    settings = get_settings()
    slug = slugify(source_key)
    last_error: Exception | None = None
    for _ in range(3):
        async with connection() as conn:
            current = await conn.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 AS version FROM documents WHERE source_key = %s",
                (source_key,),
            )
            version = int((await current.fetchone())["version"])
            doc_id = uuid.uuid4()
            filename = safe_filename(filename)
            relative = Path(slug) / f"v{version}" / filename
            root = settings.uploads_path.resolve()
            absolute = (root / relative).resolve()
            if not absolute.is_relative_to(root):
                raise RuntimeError("Upload path escapes the uploads directory")
            absolute.parent.mkdir(parents=True, exist_ok=True)
            try:
                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO documents (
                            id, source_key, version, filename, source_uri, status, storage_path
                        )
                        VALUES (%s, %s, %s, %s, %s, 'queued', %s)
                        """,
                        (doc_id, source_key, version, filename, source_uri, str(absolute)),
                    )
            except UniqueViolation as exc:
                last_error = exc
                continue
            row = await conn.execute("SELECT * FROM documents WHERE id = %s", (doc_id,))
            return _public(await row.fetchone())
    raise RuntimeError(f"Could not reserve a document version: {last_error}")


async def set_status(document_id: str, status: str, error: str | None = None) -> None:
    async with connection() as conn:
        await conn.execute(
            """
            UPDATE documents
            SET status = %s, error = %s, updated_at = now()
            WHERE id = %s
            """,
            (status, error, document_id),
        )
        await conn.commit()


async def get_document(document_id: str) -> dict[str, Any] | None:
    async with connection() as conn:
        result = await conn.execute("SELECT * FROM documents WHERE id = %s", (document_id,))
        row = await result.fetchone()
        if row is None:
            return None
        public = _public(row)
        public["chunk_count"] = await _chunk_count(conn, document_id)
        return public


async def list_documents() -> list[dict[str, Any]]:
    async with connection() as conn:
        result = await conn.execute("SELECT * FROM documents ORDER BY created_at DESC")
        rows = [_public(row) async for row in result]
        counts = await _chunk_counts(conn)
    for row in rows:
        row["chunk_count"] = counts.get(row["id"], 0)
    return rows


async def _chunk_counts(conn) -> dict[str, int]:
    table = active_chunk_table()
    exists = await conn.execute("SELECT to_regclass(%s) AS name", (table,))
    if (await exists.fetchone())["name"] is None:
        return {}
    result = await conn.execute(
        sql.SQL("SELECT document_id::text AS id, COUNT(*) AS n FROM {} GROUP BY document_id").format(
            sql.Identifier(table)
        )
    )
    return {row["id"]: int(row["n"]) async for row in result}


async def _chunk_count(conn, document_id: str) -> int:
    counts = await _chunk_counts(conn)
    return counts.get(document_id, 0)


async def _download(url: str, dest: Path) -> str | None:
    current = google_export_url(url) or url
    async with httpx.AsyncClient(timeout=45.0, follow_redirects=False) as client:
        response = None
        for _ in range(5):
            assert_public_http_url(current)
            response = await client.get(current)
            if response.status_code not in {301, 302, 303, 307, 308}:
                break
            location = response.headers.get("location")
            if not location:
                break
            current = urljoin(current, location)
        else:
            raise RuntimeError("Too many redirects")
    if response is None:
        raise RuntimeError("Download produced no response")
    if "accounts.google.com" in current:
        raise RuntimeError("Google document is not public")
    response.raise_for_status()
    if len(response.content) > _MAX_BYTES:
        raise RuntimeError("Download is larger than 20 MB")
    dest.write_bytes(response.content)
    return response.headers.get("content-type")


def _content_hash(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


async def ingest_document(document_id: str) -> None:
    """Parse one reserved document and replace its chunks. Safe to retry."""
    settings = get_settings()
    async with connection() as conn:
        result = await conn.execute("SELECT * FROM documents WHERE id = %s", (document_id,))
        row = await result.fetchone()
    if row is None:
        raise RuntimeError(f"Unknown document {document_id}")

    await set_status(document_id, "parsing", None)
    path = Path(row["storage_path"])
    content_type = None
    if not path.exists() or path.stat().st_size == 0:
        if not row["source_uri"]:
            raise RuntimeError(f"File missing at {path}")
        content_type = await _download(row["source_uri"], path)

    kind = detect(path, content_type=content_type)
    expected = suffix_for(kind)
    if path.suffix.lower() != expected:
        renamed = path.with_suffix(expected)
        path.rename(renamed)
        path = renamed
        async with connection() as conn:
            await conn.execute(
                "UPDATE documents SET storage_path = %s, filename = %s, updated_at = now() WHERE id = %s",
                (str(path), renamed.name, document_id),
            )
            await conn.commit()

    markdown = parse_file(path, kind)
    title = document_title(markdown, Path(row["filename"]).stem)
    chunks = chunk_markdown(
        markdown,
        size=settings.chunk_tokens,
        overlap=settings.chunk_overlap,
    )
    if not chunks:
        raise RuntimeError("No text could be extracted from the document")

    await set_status(document_id, "embedding", None)
    prefixed = [embed_prefix(title, chunk) for chunk in chunks]
    vectors, _usage = await embed_texts(prefixed)
    file_hash = _content_hash(path)
    source_uri = row["source_uri"] or str(path)
    table = active_chunk_table()

    async with connection() as conn:
        await ensure_chunk_table(conn, table, settings.embedding_dim)
        async with conn.transaction():
            await conn.execute(
                sql.SQL("DELETE FROM {} WHERE document_id = %s").format(sql.Identifier(table)),
                (document_id,),
            )
            for chunk, vector, embed_text in zip(chunks, vectors, prefixed, strict=True):
                chunk_hash = hashlib.sha256(chunk.content.encode()).hexdigest()
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
                    ).format(sql.Identifier(table)),
                    (
                        uuid.uuid4(),
                        document_id,
                        row["version"],
                        chunk_hash,
                        kind,
                        source_uri,
                        title,
                        chunk.header_path,
                        chunk.page_start,
                        chunk.page_end,
                        chunk.chunk_index,
                        chunk.char_start,
                        chunk.char_end,
                        settings.embedding_model,
                        chunk.content,
                        embed_text,
                        Vector(vector),
                    ),
                )
            await conn.execute(
                """
                UPDATE documents
                SET status = 'done', error = NULL, title = %s, source_type = %s,
                    source_uri = %s, content_hash = %s, updated_at = now()
                WHERE id = %s
                """,
                (title, kind, source_uri, file_hash, document_id),
            )
