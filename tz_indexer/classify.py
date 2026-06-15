from typing import Any

TYPE_MARKERS: dict[str, tuple[str, ...]] = {
    "alv_report": ("alv", "отчёт", "отчет", "report"),
    "interface": ("idoc", "ale", "интерфейс", "rfc"),
    "form": ("smartform", "adobe", "форма", "печать"),
    "enhancement": ("badi", "user-exit", "enhancement", "расширение"),
}

MODIFICATION_MARKERS: tuple[str, ...] = (
    "текущее состояние",
    "требуемые изменения",
    "было",
    "стало",
    "доработка",
)


def classify_text(text: str) -> dict[str, Any]:
    lowered = text.lower()
    tz_type = "alv_report"
    best = 0
    for candidate, markers in TYPE_MARKERS.items():
        score = sum(lowered.count(m) for m in markers)
        if score > best:
            best = score
            tz_type = candidate
    scenario = (
        "modification"
        if any(m in lowered for m in MODIFICATION_MARKERS)
        else "new"
    )
    return {"tz_type": tz_type, "scenario": scenario}
