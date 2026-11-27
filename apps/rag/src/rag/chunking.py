"""Heading-first chunking. A chunk never crosses a heading boundary."""

from __future__ import annotations

import re
from dataclasses import dataclass

import tiktoken

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_PAGE = re.compile(r"<!--\s*page:(\d+)\s*-->")
_ENCODER = tiktoken.get_encoding("cl100k_base")


@dataclass
class Chunk:
    content: str
    header_path: str
    page_start: int
    page_end: int
    chunk_index: int
    char_start: int
    char_end: int


def _token_count(text: str) -> int:
    return len(_ENCODER.encode(text))


def _decode(tokens: list[int]) -> str:
    return _ENCODER.decode(tokens)


def _split_oversized(text: str, size: int) -> list[str]:
    tokens = _ENCODER.encode(text)
    pieces = []
    for start in range(0, len(tokens), size):
        pieces.append(_decode(tokens[start : start + size]).strip())
    return [piece for piece in pieces if piece]


def _pack(text: str, size: int, overlap: int) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if not paragraphs:
        return []
    pieces: list[str] = []
    for paragraph in paragraphs:
        if _token_count(paragraph) > size:
            pieces.extend(_split_oversized(paragraph, size))
        else:
            pieces.append(paragraph)

    packed: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for piece in pieces:
        piece_tokens = _token_count(piece)
        if current and current_tokens + piece_tokens > size:
            packed.append("\n\n".join(current).strip())
            if overlap > 0:
                tail = _ENCODER.encode("\n\n".join(current))[-overlap:]
                current = [_decode(tail).strip()]
                current_tokens = _token_count(current[0])
            else:
                current = []
                current_tokens = 0
        current.append(piece)
        current_tokens += piece_tokens
    if current:
        packed.append("\n\n".join(current).strip())
    return [part for part in packed if part]


def _sections(markdown: str) -> list[tuple[str, int, int, str]]:
    """Return (header_path, page_start, page_end, text) per heading section."""
    stack: list[tuple[int, str]] = []
    page = 1
    buf: list[str] = []
    start_page = 1
    end_page = 1
    sections: list[tuple[str, int, int, str]] = []

    def path() -> str:
        return " > ".join(title for _, title in stack) or "Document"

    def flush() -> None:
        text = "\n".join(buf).strip()
        buf.clear()
        if text:
            sections.append((path(), start_page, end_page, text))

    for line in markdown.splitlines():
        page_match = _PAGE.search(line)
        if page_match and line.strip().startswith("<!--"):
            page = int(page_match.group(1))
            end_page = page
            continue
        heading = _HEADING.match(line)
        if heading:
            flush()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            start_page = page
            end_page = page
            buf.append(line)
            continue
        if not buf:
            start_page = page
        end_page = page
        buf.append(line)
    flush()
    return sections


def document_title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        heading = _HEADING.match(line)
        if heading and len(heading.group(1)) == 1:
            return heading.group(2).strip()
    return fallback


def chunk_markdown(markdown: str, *, size: int = 800, overlap: int = 100) -> list[Chunk]:
    overlap = max(0, min(overlap, size // 2))
    chunks: list[Chunk] = []
    cursor = 0
    for header_path, page_start, page_end, text in _sections(markdown):
        for part in _pack(text, size, overlap):
            found = markdown.find(part[: min(80, len(part))], max(0, cursor - 200))
            char_start = found if found >= 0 else cursor
            char_end = char_start + len(part)
            cursor = char_start + max(1, len(part) // 2)
            chunks.append(
                Chunk(
                    content=part,
                    header_path=header_path,
                    page_start=page_start,
                    page_end=page_end,
                    chunk_index=len(chunks),
                    char_start=char_start,
                    char_end=char_end,
                )
            )
    return chunks


def embed_prefix(title: str, chunk: Chunk) -> str:
    pages = (
        f"p. {chunk.page_start}"
        if chunk.page_start == chunk.page_end
        else f"p. {chunk.page_start}-{chunk.page_end}"
    )
    return f"[{title}] › {chunk.header_path} ({pages})\n{chunk.content}"
