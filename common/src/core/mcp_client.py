from contextlib import asynccontextmanager
from typing import Any

from config import settings

READ_ONLY_WHITELIST: set[str] = {
    "mcp_read_program",
    "mcp_read_table_structure",
    "mcp_search_object",
    "mcp_get_dependencies",
    "mcp_find_callers",
    "mcp_read_function_module",
    "mcp_read_class",
    "mcp_validate_object",
}

WRITE_PREFIXES: tuple[str, ...] = (
    "create_",
    "update_",
    "delete_",
    "write_",
    "modify_",
    "activate_",
    "transport_",
)


class MCPWriteBlockedError(RuntimeError):
    pass


class MCPToolNotAllowedError(RuntimeError):
    pass


def is_write_tool(name: str) -> bool:
    lowered = name.lower()
    return lowered.startswith(WRITE_PREFIXES)


def assert_read_only(name: str) -> None:
    if is_write_tool(name):
        raise MCPWriteBlockedError(f"Write-операция запрещена политикой read-only: {name}")
    if name not in READ_ONLY_WHITELIST:
        raise MCPToolNotAllowedError(f"Инструмент не в whitelist: {name}")


class MCPClient:
    def __init__(
        self,
        server_url: str | None = None,
        auth_token: str | None = None,
    ) -> None:
        self.server_url = server_url or settings.mcp.server_url
        self.auth_token = auth_token or settings.mcp.auth_token
        self._session: Any = None

    @asynccontextmanager
    async def session(self):
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        headers = {"Authorization": f"Bearer {self.auth_token}"} if self.auth_token else None
        async with streamablehttp_client(self.server_url, headers=headers) as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                self._session = session
                try:
                    yield self
                finally:
                    self._session = None

    async def list_tools(self) -> list[dict[str, Any]]:
        if self._session is None:
            raise RuntimeError("MCP session is not active")
        result = await self._session.list_tools()
        tools = []
        for tool in result.tools:
            if tool.name in READ_ONLY_WHITELIST and not is_write_tool(tool.name):
                tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description or "",
                            "parameters": tool.inputSchema or {"type": "object"},
                        },
                    }
                )
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        assert_read_only(name)
        if self._session is None:
            raise RuntimeError("MCP session is not active")
        return await self._session.call_tool(name, arguments=arguments)
