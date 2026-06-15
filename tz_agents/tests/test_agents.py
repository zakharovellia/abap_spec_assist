import pytest

from core.mcp_client import (
    MCPToolNotAllowedError,
    MCPWriteBlockedError,
    assert_read_only,
    is_write_tool,
)
from tz_agents.critic import CriticAgent
from tz_agents.diff_analyst import DiffAnalystAgent
from tz_agents.sap_explorer import SapExplorerAgent
from tz_indexer.classify import classify_text


async def test_classifier_new_default():
    from tz_agents.classifier import ClassifierAgent

    out = await ClassifierAgent().run(
        {"user_change_request": "Сделать новый отчёт по остаткам", "tz_type": "alv_report"}
    )
    assert out["scenario"] == "new"


async def test_classifier_forced_modification_by_parent():
    from tz_agents.classifier import ClassifierAgent

    out = await ClassifierAgent().run(
        {
            "user_change_request": "что-то поменять",
            "tz_type": "alv_report",
            "parent_object_ref": "program:ZRM_REPORT_01",
        }
    )
    assert out["scenario"] == "modification"


def test_mcp_write_blocked():
    assert is_write_tool("create_program")
    with pytest.raises(MCPWriteBlockedError):
        assert_read_only("update_table")


def test_mcp_not_whitelisted():
    with pytest.raises(MCPToolNotAllowedError):
        assert_read_only("some_unknown_tool")


def test_mcp_read_allowed():
    assert_read_only("mcp_read_program")


def test_explorer_limits_by_scenario():
    agent = SapExplorerAgent()
    assert agent.limits("new")[0] == 15
    assert agent.limits("modification")[0] == 25


async def test_critic_flags_missing_sections():
    out = await CriticAgent().run({"scenario": "new", "payload": {}})
    assert out["critic_report"]["status"] == "needs_revision"
    assert out["critic_iterations"] == 1


async def test_diff_analyst_inferred_when_no_legacy():
    out = await DiffAnalystAgent().run(
        {"legacy_tz": {"provided": False}, "current_state_analysis": {"code_summary": "x"}}
    )
    assert "inferred_behavior" in out["diff_analysis"]


def test_indexer_classify_modification():
    result = classify_text("Текущее состояние ... Требуемые изменения ... доработка отчёта")
    assert result["scenario"] == "modification"
