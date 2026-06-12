from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.core.config import settings


def get_chat_model(model: str, temperature: float = 0.3) -> BaseChatModel:
    """
    Get a chat model instance.
    
    Args:
        model: The model name to use
        temperature: The temperature for the model
        
    Returns:
        A ChatOpenAI instance
    """
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=settings.openai_api_key or None,
    )
