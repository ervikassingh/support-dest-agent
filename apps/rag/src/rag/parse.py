"""Turn a supported file into Markdown with `<!-- page:N -->` markers."""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup
from docx import Document
from docx.oxml.ns import qn
from markdownify import markdownify
from pypdf import PdfReader


def _with_page(text: str, page: int = 1) -> str:
    body = text.strip()
    if "<!-- page:" in body:
        return body
    return f"<!-- page:{page} -->\n{body}"


def parse_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    parts: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        raw = page.extract_text() or ""
        lines = [line.strip() for line in raw.splitlines()]
        parts.append(f"<!-- page:{index} -->\n" + "\n".join(lines))
    return "\n\n".join(parts).strip()


def parse_docx(path: Path) -> str:
    document = Document(str(path))
    page = 1
    lines = [f"<!-- page:{page} -->"]
    for paragraph in document.paragraphs:
        breaks = paragraph._p.findall(".//" + qn("w:br"))
        for item in breaks:
            if item.get(qn("w:type")) == "page":
                page += 1
                lines.append(f"<!-- page:{page} -->")
        if "lastRenderedPageBreak" in paragraph._p.xml and 'w:type="page"' not in paragraph._p.xml:
            page += 1
            lines.append(f"<!-- page:{page} -->")
        text = paragraph.text.strip()
        if not text:
            continue
        style = paragraph.style.name if paragraph.style is not None else ""
        if style.startswith("Heading"):
            try:
                level = int(style.split()[-1])
            except ValueError:
                level = 1
            lines.append(f"{'#' * max(1, min(level, 6))} {text}")
        else:
            lines.append(text)
        lines.append("")
    return "\n".join(lines).strip()


def parse_html(path: Path) -> str:
    raw = path.read_text(errors="ignore")
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup.find_all(["script", "style", "noscript"]):
        tag.decompose()
    title = soup.title.get_text(strip=True) if soup.title else ""
    body = markdownify(str(soup.body or soup), heading_style="ATX").strip()
    if title and not body.lstrip().startswith("# "):
        body = f"# {title}\n\n{body}"
    return _with_page(body)


def parse_text(path: Path) -> str:
    return _with_page(path.read_text(errors="ignore"))


def parse_file(path: Path, kind: str) -> str:
    if kind == "pdf":
        return parse_pdf(path)
    if kind == "docx":
        return parse_docx(path)
    if kind == "html":
        return parse_html(path)
    return parse_text(path)
