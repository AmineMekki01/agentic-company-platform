import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.llm import get_chat_model
from app.core.config import settings

logger = logging.getLogger(__name__)

_TITLE_PROMPT = (
    "Generate a very short title (3-6 words, no quotes, no trailing period) "
    "summarizing the user's message. Use the same language as the message."
)


def _truncate(text: str, limit: int = 60) -> str:
    """
    Truncate text to a maximum length, adding an ellipsis if needed.
    
    Args:
        text: Text to truncate
        limit: Maximum length of the text
        
    Returns:
        str: Truncated text
    """
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


async def generate_title(first_message: str) -> str:
    """
    Generate a short conversation title from the first user message.
    
    Args:
        first_message: First user message
        
    Returns:
        str: Generated title
    """
    if not settings.openai_api_key:
        return _truncate(first_message)

    try:
        llm = get_chat_model("gpt-5.4-nano", temperature=0.2)
        response = await llm.ainvoke(
            [SystemMessage(content=_TITLE_PROMPT), HumanMessage(content=first_message[:2000])]
        )
        title = str(response.content).strip().strip('"').strip()
        return _truncate(title) if title else _truncate(first_message)
    except Exception:
        logger.exception("Title generation failed, falling back to truncation")
        return _truncate(first_message)
