from pathlib import Path
from typing import Any

from core.base_agent import BaseAgent

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"

LEGACY_WARNING = (
    "ТЗ создано без приложения исходного ТЗ. Описание текущего поведения "
    "реконструировано на основе анализа кода и может содержать неточности в части "
    "бизнес-обоснований. Перед использованием рекомендуется ревью consultant-автором."
)


class RendererAgent(BaseAgent):
    name = "renderer"
    tier = "small"

    def template_for(self, tz_type: str, scenario: str) -> Path:
        return TEMPLATES_DIR / f"{tz_type}_{scenario}.docx"

    def build_context(self, state: dict[str, Any]) -> dict[str, Any]:
        scenario = state.get("scenario", "new")
        legacy_provided = bool((state.get("legacy_tz") or {}).get("provided"))
        return {
            "payload": state.get("payload") or {},
            "scenario": scenario,
            "research_log": state.get("research_log") or [],
            "diff_analysis": state.get("diff_analysis") or {},
            "legacy_warning": LEGACY_WARNING
            if scenario == "modification" and not legacy_provided
            else None,
        }

    def render_to_path(self, state: dict[str, Any], out_path: Path) -> Path:
        from docxtpl import DocxTemplate

        tz_type = state.get("tz_type") or "alv_report"
        scenario = state.get("scenario", "new")
        template_path = self.template_for(tz_type, scenario)
        doc = DocxTemplate(str(template_path))
        doc.render(self.build_context(state))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(out_path))
        return out_path

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        tz_id = state.get("tz_id")
        revision = "draft"
        object_key = f"tz/{tz_id}/{revision}.docx"
        return {"docx_object_key": object_key, "status": "finalized"}
