import asyncio
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.core.config import settings

OLLAMA_PREFIX = "ollama/"

_api_semaphore = asyncio.Semaphore(settings.llm_api_concurrency)
_local_semaphore = asyncio.Semaphore(settings.llm_local_concurrency)


class _ConcurrencyLimitedChatModel:
    """Wraps a ChatOpenAI and gates concurrent calls via a semaphore."""

    def __init__(self, model: ChatOpenAI, semaphore: asyncio.Semaphore) -> None:
        self._model = model
        self._semaphore = semaphore

    def __getattr__(self, name: str) -> Any:
        return getattr(self._model, name)

    async def ainvoke(self, messages: Any, **kwargs: Any) -> Any:
        async with self._semaphore:
            return await self._model.ainvoke(messages, **kwargs)

    async def astream(self, messages: Any, **kwargs: Any) -> AsyncIterator[Any]:
        async with self._semaphore:
            async for chunk in self._model.astream(messages, **kwargs):
                yield chunk

    def bind_tools(self, tools: Any, **kwargs: Any) -> "_ConcurrencyLimitedChatModel":
        return _ConcurrencyLimitedChatModel(
            self._model.bind_tools(tools, **kwargs),
            self._semaphore,
        )


def get_chat_model(model: str, temperature: float = 0.3) -> BaseChatModel:
    """
    Get a chat model instance.

    If the model name is prefixed with 'ollama/' (e.g. 'ollama/qwen3.5:2b'),
    the prefix is stripped and the request is routed to the Ollama
    OpenAI-compatible endpoint.

    Args:
        model: The model name to use (optionally prefixed with 'ollama/')
        temperature: The temperature for the model

    Returns:
        A ChatOpenAI instance configured for the appropriate provider
    """
    if model.startswith(OLLAMA_PREFIX):
        actual_model = model[len(OLLAMA_PREFIX):]
        raw = ChatOpenAI(
            model=actual_model,
            temperature=temperature,
            api_key="ollama",
            base_url=settings.ollama_base_url,
            timeout=settings.llm_local_timeout,
            max_retries=settings.llm_max_retries,
        )
        return _ConcurrencyLimitedChatModel(raw, _local_semaphore)

    raw = ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=settings.openai_api_key or None,
        timeout=settings.llm_timeout,
        max_retries=settings.llm_max_retries,
    )
    return _ConcurrencyLimitedChatModel(raw, _api_semaphore)
