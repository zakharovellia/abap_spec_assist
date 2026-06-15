from pathlib import Path
from typing import Any

from core.docx_parse import parse_docx_structure


def parse(file_path: str | Path) -> dict[str, Any]:
    return parse_docx_structure(file_path)
