"""Оригинальный .docx сессии и экспорт «патчем оригинала».

Проблема: путь docx → Markdown → docx лоссовый — при полной регенерации
пользователь терял корпоративный шаблон, титульный лист, колонтитулы,
картинки и стили. Поэтому загруженный .docx сохраняется как есть, а рядом —
карта «id раздела → диапазон блоков (абзацев/таблиц) оригинала». Агент
по-прежнему работает с Markdown-разделами; при экспорте в оригинале
заменяются ТОЛЬКО диапазоны изменённых разделов (новый текст оформляется
стилями самого документа), нетронутые разделы — вместе с картинками и
форматированием — остаются как были.

Ограничения (осознанные):
- внутри изменённого раздела картинки и тонкое форматирование заменяются
  сгенерированным текстом — цена правки, а не порча всего документа;
- если автонарезка разрезала документ не по границам абзацев (_hard_wrap на
  аномально длинных абзацах), карта не строится и экспорт честно падает
  обратно на полную регенерацию из Markdown.
"""

import hashlib
import io
import json
import logging
from pathlib import Path

from docx import Document

from app import spec_doc
from app.config import settings
from app.docx_parse import append_markdown, markdown_to_docx

logger = logging.getLogger(__name__)


def _paths(session_id: str) -> tuple[Path, Path]:
    base = Path(settings.originals_dir)
    return base / f"{session_id}.docx", base / f"{session_id}.json"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def save_original(
    session_id: str,
    data: bytes,
    sections: list[dict],
    blocks: list[tuple[int, str]],
) -> bool:
    """Сохраняет оригинал и карту разделов; False — карта не сошлась
    (экспорт этой сессии пойдёт полной регенерацией)."""
    mapping = _map_sections(sections, blocks)
    if mapping is None:
        delete_original(session_id)
        logger.info(
            "Сессия %s: карта разделов оригинала не построилась, "
            "экспорт будет полной регенерацией",
            session_id,
        )
        return False
    docx_path, map_path = _paths(session_id)
    docx_path.parent.mkdir(parents=True, exist_ok=True)
    docx_path.write_bytes(data)
    map_path.write_text(json.dumps({"sections": mapping}, ensure_ascii=False))
    return True


def _map_sections(
    sections: list[dict], blocks: list[tuple[int, str]]
) -> list[dict] | None:
    """Каждому разделу — диапазон [start, end] контентных блоков оригинала.

    Тела разделов — соединения markdown-блоков через пустую строку, поэтому
    сопоставление идёт последовательным поглощением блоков. Любой рассинхрон
    (граница раздела внутри блока после _hard_wrap) — карта не строится
    целиком: частичная карта дала бы неоднозначный патч.
    """
    bi = 0
    out: list[dict] = []
    for s in sections:
        paras = [p.strip() for p in s["body"].split("\n\n") if p.strip()]
        start: int | None = None
        end = 0
        for para in paras:
            if bi >= len(blocks) or blocks[bi][1] != para:
                return None
            idx = blocks[bi][0]
            start = idx if start is None else start
            end = idx
            bi += 1
        if start is None:
            return None
        out.append({"id": s["id"], "start": start, "end": end, "sha": _sha(s["body"])})
    if bi != len(blocks):
        return None
    return out


def delete_original(session_id: str) -> None:
    for path in _paths(session_id):
        path.unlink(missing_ok=True)


def export_docx(session_id: str, sections: list[dict]) -> bytes:
    """Экспорт документа сессии: патч оригинала, если он есть и удался,
    иначе полная регенерация из Markdown."""
    docx_path, map_path = _paths(session_id)
    if docx_path.exists() and map_path.exists():
        try:
            mapping = json.loads(map_path.read_text())["sections"]
            return _patch(docx_path.read_bytes(), mapping, sections)
        except Exception:  # noqa: BLE001 — патч вспомогательный, документ отдаём всегда
            logger.warning(
                "Сессия %s: патч оригинала не удался, полная регенерация",
                session_id,
                exc_info=True,
            )
    return markdown_to_docx(spec_doc.render_markdown(sections))


def _patch(data: bytes, mapping: list[dict], sections: list[dict]) -> bytes:
    doc = Document(io.BytesIO(data))
    body = doc.element.body
    # держим ссылки на прокси lxml: пока они живы, повторные обходы возвращают
    # те же объекты и работает сравнение по идентичности
    children = [
        c for c in body.iterchildren() if c.tag.endswith("}p") or c.tag.endswith("}tbl")
    ]
    by_id = {e["id"]: e for e in mapping}
    cursor = None  # элемент, после которого вставлять новый контент; None = начало body
    current_ids: set[str] = set()
    for s in sections:
        current_ids.add(s["id"])
        entry = by_id.get(s["id"])
        if entry is not None:
            elems = children[entry["start"] : entry["end"] + 1]
            if _sha(s["body"]) == entry["sha"]:
                cursor = elems[-1]  # раздел не менялся — оригинальные блоки на месте
                continue
            new_elems = _render(doc, s["body"])
            anchor = elems[0]
            fallback_cursor = anchor.getprevious()
            for ne in new_elems:
                anchor.addprevious(ne)
            for old in elems:
                body.remove(old)
            cursor = new_elems[-1] if new_elems else fallback_cursor
        else:
            new_elems = _render(doc, s["body"])
            if cursor is None:
                for ne in reversed(new_elems):
                    body.insert(0, ne)
            else:
                prev = cursor
                for ne in new_elems:
                    prev.addnext(ne)
                    prev = ne
            if new_elems:
                cursor = new_elems[-1]
    # разделы, удалённые агентом, — убрать их блоки из оригинала
    for entry in mapping:
        if entry["id"] not in current_ids:
            for old in children[entry["start"] : entry["end"] + 1]:
                if old.getparent() is not None:
                    old.getparent().remove(old)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _render(doc: Document, markdown: str) -> list:
    """Markdown → элементы документа стилями самого документа. append_markdown
    добавляет их в конец body (перед sectPr) — возвращаем новые элементы,
    вызывающий переставит их на нужное место."""
    before = list(doc.element.body.iterchildren())
    append_markdown(doc, markdown)
    before_set = set(id(c) for c in before)
    return [c for c in doc.element.body.iterchildren() if id(c) not in before_set]
