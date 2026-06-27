from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.core.config import settings

OLLAMA_PREFIX = "ollama/"


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
        return ChatOpenAI(
            model=actual_model,
            temperature=temperature,
            api_key="ollama",
            base_url=settings.ollama_base_url,
        )

    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=settings.openai_api_key or None,
    )
