"""Подключение MCP-сервера ADT tools (чтение объектов SAP).

Агенту отдаются только read-only инструменты: всё, что похоже на запись
(create_/update_/delete_/activate_/transport_ и т.п.), отфильтровывается —
ассистент пишет ТЗ и не имеет права менять объекты в системе.
"""

import logging

from langchain_core.tools import BaseTool

from app.config import settings

logger = logging.getLogger(__name__)

WRITE_PREFIXES: tuple[str, ...] = (
    "create_",
    "update_",
    "delete_",
    "write_",
    "modify_",
    "activate_",
    "transport_",
    "insert_",
    "execute_",
)


def is_write_tool(name: str) -> bool:
    lowered = name.lower().removeprefix("mcp_")
    return lowered.startswith(WRITE_PREFIXES)


async def load_sap_tools() -> list[BaseTool]:
    if not settings.mcp_server_url:
        logger.info("MCP: MCP_SERVER_URL не задан, работаем без SAP-инструментов")
        return []
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        connection: dict = {
            "transport": settings.mcp_transport,
            "url": settings.mcp_server_url,
        }
        if settings.mcp_auth_token:
            connection["headers"] = {
                "Authorization": f"Bearer {settings.mcp_auth_token}"
            }
        client = MultiServerMCPClient({"adt": connection})
        tools = await client.get_tools()
    except Exception:
        logger.warning(
            "MCP-сервер %s недоступен, работаем без SAP-инструментов",
            settings.mcp_server_url,
            exc_info=True,
        )
        return []

    readonly = [t for t in tools if not is_write_tool(t.name)]
    blocked = sorted(t.name for t in tools if is_write_tool(t.name))
    if blocked:
        logger.info("MCP: заблокированы пишущие инструменты: %s", ", ".join(blocked))
    logger.info(
        "MCP: подключено %d SAP-инструментов: %s",
        len(readonly),
        ", ".join(t.name for t in readonly),
    )
    return readonly
