"""Документ ТЗ как список адресуемых разделов, а не одна строка Markdown.

Нужно для больших документов (сотни тысяч слов): агенту в промпт попадает
оглавление и несколько релевантных разделов, а не документ целиком — иначе
он физически не влезает в контекст LLM. Правки вносятся точечно
(update_section/insert_section/delete_section), без необходимости
перегенерировать весь текст на каждый ход (см. app/graph/builder.py).

Нарезка на разделы работает в три уровня, каждый — страховка от того, что
предыдущий не сработает на документе без чёткой структуры:
1. Markdown-заголовки (#..######), доставшиеся от doc_parse.py.
2. Эвристики по тексту абзацев: нумерация верхнего уровня («1. …»), абзац
   целиком жирным, строка КАПСОМ — на случай, если в исходном .docx не
   использовались стили заголовков Word (частый случай в реальных ТЗ).
3. Фиксированное окно по границам абзацев — если в документе вообще нет
   уловимой структуры («идёт сплошняком»).

После любого из трёх способов раздел, превышающий settings.spec_max_section_chars,
принудительно дробится дальше (эвристиками, потом окном) — так один
нераспознанный H1 на весь документ не может привести к «одному разделу на
200 000 слов».
"""

import re
import uuid

from app.config import settings

_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
_TOP_NUMBERED_RE = re.compile(r"^\d{1,2}\.\s+\S.{0,100}$")
_BOLD_LINE_RE = re.compile(r"^\*\*(.+)\*\*$")
_HEURISTIC_MIN_HITS = 2
_FIXED_CHUNK_CHARS = 6000


def new_id() -> str:
    return uuid.uuid4().hex[:8]


def _make_section(level: int, title: str, body: str, *, synthetic: bool = False) -> dict:
    return {
        "id": new_id(),
        "level": level,
        "title": title,
        "body": body.strip(),
        "synthetic": synthetic,
    }


def parse_sections(markdown: str) -> list[dict]:
    """Разбивает Markdown документа ТЗ на список разделов (см. модуль)."""
    markdown = markdown.strip()
    if not markdown:
        return []
    sections = (
        _split_by_markdown_headings(markdown)
        or _split_by_heuristics(markdown)
        or _split_fixed(markdown)
    )
    return _enforce_max_size(sections)


def _split_by_markdown_headings(markdown: str) -> list[dict] | None:
    matches = list(_MD_HEADING_RE.finditer(markdown))
    if not matches:
        return None
    by_level: dict[int, list] = {}
    for m in matches:
        by_level.setdefault(len(m.group(1)), []).append(m)
    # Берём самый верхний уровень, который встречается хотя бы дважды —
    # единственный H1-заголовок обычно название документа, а не граница
    # раздела (иначе весь документ схлопнется в одну "секцию").
    top_level = next(
        (lvl for lvl in sorted(by_level) if len(by_level[lvl]) >= 2), min(by_level)
    )
    top_matches = by_level[top_level]

    sections: list[dict] = []
    preamble = markdown[: top_matches[0].start()].strip()
    if preamble:
        sections.append(_make_section(1, "Преамбула", preamble, synthetic=True))
    for m, nxt in zip(top_matches, [*top_matches[1:], None]):
        end = nxt.start() if nxt else len(markdown)
        body = markdown[m.start() : end].strip()
        if body:
            sections.append(_make_section(top_level, m.group(2).strip(), body))
    return sections or None


def _split_by_heuristics(markdown: str) -> list[dict] | None:
    paragraphs = [p for p in markdown.split("\n\n") if p.strip()]
    boundaries: list[tuple[int, str]] = []
    for i, para in enumerate(paragraphs):
        line = para.strip()
        if "\n" in line:
            continue
        if m := _BOLD_LINE_RE.match(line):
            boundaries.append((i, m.group(1).strip()))
        elif _TOP_NUMBERED_RE.match(line):
            boundaries.append((i, line))
        elif _looks_all_caps(line):
            boundaries.append((i, line))
    if len(boundaries) < _HEURISTIC_MIN_HITS:
        return None

    sections: list[dict] = []
    preamble = "\n\n".join(paragraphs[: boundaries[0][0]]).strip()
    if preamble:
        sections.append(_make_section(1, "Преамбула", preamble, synthetic=True))
    for (idx, title), nxt in zip(boundaries, [*boundaries[1:], None]):
        end = nxt[0] if nxt else len(paragraphs)
        body = "\n\n".join(paragraphs[idx:end]).strip()
        if body:
            sections.append(_make_section(1, title, body, synthetic=True))
    return sections or None


def _looks_all_caps(line: str) -> bool:
    if len(line) > 100 or len(line.split()) > 12:
        return False
    letters = [c for c in line if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters)


def _split_fixed(markdown: str) -> list[dict]:
    paragraphs = [p for p in markdown.split("\n\n") if p.strip()] or [markdown]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        for piece in _hard_wrap(para):
            if current and len(current) + len(piece) + 2 > _FIXED_CHUNK_CHARS:
                chunks.append(current)
                current = piece
            else:
                current = f"{current}\n\n{piece}" if current else piece
    if current:
        chunks.append(current)
    return [
        _make_section(1, f"Фрагмент {i}", body, synthetic=True)
        for i, body in enumerate(chunks, 1)
    ]


def _hard_wrap(paragraph: str) -> list[str]:
    """Режет один аномально длинный абзац (без внутренних пустых строк) по
    границе слов — последняя страховка для сплошного текста вообще без
    пустых строк, где разбиение по абзацам не помогает."""
    if len(paragraph) <= _FIXED_CHUNK_CHARS:
        return [paragraph]
    words = paragraph.split(" ")
    pieces: list[str] = []
    current = ""
    for w in words:
        if current and len(current) + len(w) + 1 > _FIXED_CHUNK_CHARS:
            pieces.append(current)
            current = w
        else:
            current = f"{current} {w}" if current else w
    if current:
        pieces.append(current)
    return pieces


def _enforce_max_size(sections: list[dict]) -> list[dict]:
    """Гарантирует, что ни один раздел не превышает spec_max_section_chars —
    страховка на случай, если предыдущий уровень разбивки нашёл слишком
    крупные "разделы" (например, единственный H1 на весь документ)."""
    limit = settings.spec_max_section_chars
    out: list[dict] = []
    for s in sections:
        if len(s["body"]) <= limit:
            out.append(s)
            continue
        sub = _split_by_heuristics(s["body"]) or _split_fixed(s["body"])
        if len(sub) <= 1:
            out.append(s)
            continue
        for i, part in enumerate(sub, 1):
            out.append(
                {
                    **part,
                    "title": f"{s['title']} — часть {i}",
                    "level": s["level"],
                    "synthetic": True,
                }
            )
    return out


def render_markdown(sections: list[dict]) -> str:
    """Полный текст документа — для превью на фронтенде и экспорта."""
    return "\n\n".join(s["body"] for s in sections).strip()


def render_toc(sections: list[dict]) -> str:
    if not sections:
        return "(документ пока пуст)"
    lines = []
    for s in sections:
        flag = " ⚠ структура не распознана автоматически" if s.get("synthetic") else ""
        words = len(s["body"].split())
        lines.append(f"- [{s['id']}] {s['title']} (~{words} слов){flag}")
    return "\n".join(lines)


def render_section(section: dict) -> str:
    return section["body"]


def render_relevant(sections: list[dict], ids: list[str]) -> str:
    by_id = {s["id"]: s for s in sections}
    picked = [by_id[i] for i in ids if i in by_id]
    if not picked:
        return "(ни один раздел не выбран автоматически — используй list_sections/get_section)"
    blocks = [f"### [{s['id']}] {s['title']}\n\n{s['body']}" for s in picked]
    return "\n\n---\n\n".join(blocks)


def find_section(sections: list[dict], section_id: str) -> dict | None:
    return next((s for s in sections if s["id"] == section_id), None)


def update_section(sections: list[dict], section_id: str, new_text: str) -> tuple[list[dict], bool]:
    out: list[dict] = []
    found = False
    for s in sections:
        if s["id"] == section_id:
            found = True
            heading = _derive_heading(new_text)
            level, title = heading if heading else (s["level"], s["title"])
            out.append({**s, "level": level, "title": title, "body": new_text.strip(), "synthetic": False})
        else:
            out.append(s)
    return out, found


def insert_section(
    sections: list[dict],
    after_section_id: str | None,
    level: int,
    title: str,
    body: str,
) -> tuple[list[dict], str]:
    level = max(1, min(level, 6))
    heading = f"{'#' * level} {title}"
    full_body = f"{heading}\n\n{body.strip()}" if body.strip() else heading
    new_section = _make_section(level, title, full_body)
    out = list(sections)
    if after_section_id is None:
        out.insert(0, new_section)
    else:
        idx = next((i for i, s in enumerate(out) if s["id"] == after_section_id), None)
        out.insert(idx + 1 if idx is not None else len(out), new_section)
    return out, new_section["id"]


def delete_section(sections: list[dict], section_id: str) -> tuple[list[dict], bool]:
    out = [s for s in sections if s["id"] != section_id]
    return out, len(out) != len(sections)


def _derive_heading(text: str) -> tuple[int, str] | None:
    stripped = text.strip()
    if not stripped:
        return None
    first_line = stripped.splitlines()[0]
    if m := re.match(r"^(#{1,6})\s+(.*)$", first_line):
        return len(m.group(1)), m.group(2).strip()
    return None
