from pathlib import Path
from typing import Any

SECTION_ALIASES: dict[str, str] = {
    "шапка": "header",
    "метаданные": "header",
    "бизнес-контекст": "business_context",
    "цель": "business_context",
    "источники данных": "data_sources",
    "источник данных": "data_sources",
    "экран выбора": "selection_screen",
    "параметры отбора": "selection_screen",
    "алгоритм": "algorithm",
    "алгоритм работы": "algorithm",
    "порядок работы": "algorithm",
    "вывод": "output_layout",
    "выходная форма": "output_layout",
    "макет вывода": "output_layout",
    "авторизации": "authorizations",
    "обработка ошибок": "error_handling",
    "тест-кейсы": "test_cases",
    "тестовые сценарии": "test_cases",
    "дополнения": "additions",
}


def normalize_heading(heading: str) -> tuple[str | None, bool]:
    key = heading.strip().lower().rstrip(".:")
    if key in SECTION_ALIASES:
        return SECTION_ALIASES[key], False
    for alias, section in SECTION_ALIASES.items():
        if alias in key:
            return section, True
    return None, True


def parse_docx_structure(file_path: str | Path) -> dict[str, Any]:
    from docx import Document

    doc = Document(str(file_path))
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    raw_parts: list[str] = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        raw_parts.append(text)
        style = (para.style.name or "").lower() if para.style else ""
        if style.startswith("heading") or style.startswith("заголовок"):
            section, low_conf = normalize_heading(text)
            current = {
                "heading": text,
                "section_type": section,
                "confidence_low": low_conf,
                "paragraphs": [],
            }
            sections.append(current)
        else:
            if current is None:
                current = {
                    "heading": "",
                    "section_type": None,
                    "confidence_low": True,
                    "paragraphs": [],
                }
                sections.append(current)
            current["paragraphs"].append(text)

    return {"sections": sections, "raw_text": "\n".join(raw_parts)}
