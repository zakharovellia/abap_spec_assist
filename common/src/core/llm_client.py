from typing import Any, Literal

from openai import AsyncOpenAI

from config import settings

ModelTier = Literal["small", "medium", "strong"]

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url=settings.llm.base_url,
            api_key=settings.llm.api_key or "not-needed",
            timeout=settings.llm.timeout_seconds,
        )
    return _client


def resolve_model(tier: ModelTier) -> str:
    mapping = {
        "small": settings.llm.model_small,
        "medium": settings.llm.model_medium,
        "strong": settings.llm.model_strong,
    }
    return mapping[tier]


async def chat(
    messages: list[dict[str, Any]],
    *,
    tier: ModelTier = "medium",
    tools: list[dict[str, Any]] | None = None,
    temperature: float | None = None,
    response_format: dict[str, Any] | None = None,
    tool_choice: str | dict[str, Any] | None = None,
) -> Any:
    client = get_client()
    kwargs: dict[str, Any] = {
        "model": resolve_model(tier),
        "messages": messages,
        "temperature": settings.llm.temperature_default
        if temperature is None
        else temperature,
    }
    if tools:
        kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
    if response_format:
        kwargs["response_format"] = response_format
    return await client.chat.completions.create(**kwargs)


async def chat_stream(
    messages: list[dict[str, Any]],
    *,
    tier: ModelTier = "medium",
    temperature: float | None = None,
):
    client = get_client()
    stream = await client.chat.completions.create(
        model=resolve_model(tier),
        messages=messages,
        temperature=settings.llm.temperature_default if temperature is None else temperature,
        stream=True,
    )
    async for chunk in stream:
        yield chunk
