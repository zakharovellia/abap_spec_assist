from pathlib import Path
from typing import Any

from core.llm_client import ModelTier, chat

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "tz_agents" / "prompts"


def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


class BaseAgent:
    name: str = "base"
    tier: ModelTier = "medium"
    temperature: float | None = None
    prompt_file: str | None = None

    def system_prompt(self, **_: Any) -> str:
        if self.prompt_file:
            return load_prompt(self.prompt_file)
        return ""

    def tools(self) -> list[dict[str, Any]] | None:
        return None

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        response_format: dict[str, Any] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> Any:
        return await chat(
            messages,
            tier=self.tier,
            tools=self.tools(),
            temperature=self.temperature,
            response_format=response_format,
            tool_choice=tool_choice,
        )

    def build_messages(self, user_content: str, **prompt_kwargs: Any) -> list[dict[str, Any]]:
        return [
            {"role": "system", "content": self.system_prompt(**prompt_kwargs)},
            {"role": "user", "content": user_content},
        ]
