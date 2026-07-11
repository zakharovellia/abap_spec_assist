"""Конвертация загруженного файла ТЗ (.docx / .md / .txt) в Markdown."""

import io
import re

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


def file_to_markdown(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".docx"):
        return docx_to_markdown(data)
    if name.endswith((".md", ".markdown", ".txt")):
        return data.decode("utf-8", errors="replace")
    raise ValueError(f"Неподдерживаемый формат файла: {filename}")


def docx_to_markdown(data: bytes) -> str:
    doc = Document(io.BytesIO(data))
    lines: list[str] = []
    for block in _iter_blocks(doc):
        if isinstance(block, Paragraph):
            md = _paragraph_to_md(block)
            if md is not None:
                lines.append(md)
        elif isinstance(block, Table):
            lines.append(_table_to_md(block))
    return "\n\n".join(lines).strip()


def _iter_blocks(doc):
    for child in doc.element.body.iterchildren():
        if child.tag.endswith("}p"):
            yield Paragraph(child, doc)
        elif child.tag.endswith("}tbl"):
            yield Table(child, doc)


_HEADING_RE = re.compile(r"(?:heading|заголовок)\s*(\d)", re.IGNORECASE)
_LIST_RE = re.compile(r"list|список|маркированный|нумерованный", re.IGNORECASE)


def _paragraph_to_md(p: Paragraph) -> str | None:
    text = p.text.strip()
    if not text:
        return None
    style = p.style.name if p.style is not None else ""
    if m := _HEADING_RE.search(style):
        level = min(int(m.group(1)), 6)
        return f"{'#' * level} {text}"
    if _LIST_RE.search(style):
        return f"- {text}"
    return text


def _table_to_md(table: Table) -> str:
    rows: list[list[str]] = []
    for row in table.rows:
        rows.append([" ".join(cell.text.split()) for cell in row.cells])
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    out = ["| " + " | ".join(rows[0]) + " |", "|" + " --- |" * width]
    out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(out)
