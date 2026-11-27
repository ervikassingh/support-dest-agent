"""File-type detection and public Google export URLs."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

_GOOGLE_EXPORTS = (
    ("document", "pdf"),
    ("spreadsheets", "pdf"),
    ("presentation", "pdf"),
)

_SUFFIX = {
    "pdf": ".pdf",
    "docx": ".docx",
    "html": ".html",
    "md": ".md",
    "txt": ".txt",
}


def google_export_url(url: str) -> str | None:
    """Rewrite a public Google Docs, Sheets, or Slides link to a PDF export."""
    for kind, fmt in _GOOGLE_EXPORTS:
        match = re.search(rf"docs\.google\.com/{kind}/d/([^/]+)", url)
        if match:
            return f"https://docs.google.com/{kind}/d/{match.group(1)}/export?format={fmt}"
    return None


def suffix_for(kind: str) -> str:
    return _SUFFIX.get(kind, ".bin")


def _is_docx(path: Path) -> bool:
    if not zipfile.is_zipfile(path):
        return False
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
    return any(name.startswith("word/") for name in names)


def detect(path: Path, content_type: str | None = None, hint: str | None = None) -> str:
    """Return pdf, docx, html, md, or txt."""
    ext = (hint or path.suffix).lower()
    if not ext.startswith(".") and ext:
        ext = f".{ext}"
    media = (content_type or "").split(";")[0].strip().lower()
    head = path.read_bytes()[:8]

    if head.startswith(b"%PDF") or ext == ".pdf" or media == "application/pdf":
        return "pdf"
    if ext == ".docx" or media.endswith("wordprocessingml.document") or (
        head.startswith(b"PK") and _is_docx(path)
    ):
        return "docx"
    if ext in {".html", ".htm"} or media == "text/html":
        return "html"
    if ext == ".md" or media == "text/markdown":
        return "md"
    sample = path.read_text(errors="ignore")[:800].lower()
    if "<html" in sample or "<!doctype html" in sample:
        return "html"
    if ext == ".txt" or media.startswith("text/"):
        return "txt"
    return "txt"
