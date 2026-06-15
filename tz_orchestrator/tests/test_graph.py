from schemas.tz_state import TzState
from tz_orchestrator.graph import build_graph


async def _run(document: dict, message: str) -> dict:
    graph = build_graph()
    compiled = graph.compile()
    state = TzState(
        tz_id="t1",
        author_id=document["author_id"],
        tz_type=document.get("tz_type"),
        scenario=document.get("scenario", "new"),
        parent_object_ref=document.get("parent_object_ref"),
        user_change_request=message,
    )
    result = await compiled.ainvoke(state)
    return result if isinstance(result, dict) else result.model_dump()


async def test_new_scenario_end_to_end():
    result = await _run(
        {"author_id": "ivanov", "tz_type": "alv_report", "scenario": "new"},
        "Нужен новый ALV-отчёт по остаткам MARD",
    )
    assert result["scenario"] == "new"
    assert result["status"] == "finalized"
    assert result["docx_object_key"].startswith("tz/")
    assert result["payload"].get("algorithm")
    assert result["research_log"]


async def test_modification_scenario_routes_through_diff():
    result = await _run(
        {
            "author_id": "petrov",
            "tz_type": "alv_report",
            "scenario": "modification",
            "parent_object_ref": "program:ZRM_REPORT_01",
        },
        "Доработать отчёт ZRM_REPORT_01: добавить поле даты",
    )
    assert result["scenario"] == "modification"
    assert result["diff_analysis"]
    assert result["status"] == "finalized"


async def test_classifier_detects_modification_by_trigger():
    from tz_agents.classifier import ClassifierAgent

    out = await ClassifierAgent().run(
        {"user_change_request": "Нужно доработать отчёт", "tz_type": "alv_report"}
    )
    assert out["scenario"] == "modification"
