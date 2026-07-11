"""LLM tracing via Langfuse."""

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

_handler = None
_handler_init_attempted = False


def get_langfuse_handler():
    """Return a shared Langfuse CallbackHandler, or None if tracing is disabled
    or failed to initialize. Never raises.
    """
    global _handler, _handler_init_attempted

    if _handler_init_attempted:
        return _handler

    _handler_init_attempted = True
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None

    try:
        from langfuse.langchain import CallbackHandler

        _handler = CallbackHandler()
    except Exception:
        logger.warning("Langfuse handler init failed, tracing disabled", exc_info=True)
        _handler = None

    return _handler


def trace_config(
    config: dict,
    *,
    conversation_id: str | None = None,
    user_id: str | None = None,
    agent_slug: str | None = None,
    tags: list[str] | None = None,
    handler=None,
) -> dict:
    """Return a copy of config with a Langfuse callback + trace metadata merged
    in, if tracing is enabled. Returns config unchanged otherwise - callers
    never need an `if` branch around this.

    Pass an explicit `handler` (from new_langfuse_handler()) when the caller
    needs to read back this specific call's trace id afterward (e.g. to show a
    "view trace" link) - otherwise the shared cached handler is used.
    """
    handler = handler if handler is not None else get_langfuse_handler()
    if handler is None:
        return config

    try:
        merged = dict(config)
        merged["callbacks"] = [*config.get("callbacks", []), handler]
        merged["metadata"] = {
            **config.get("metadata", {}),
            "langfuse_session_id": conversation_id,
            "langfuse_user_id": user_id,
            "langfuse_tags": [t for t in [agent_slug, *(tags or [])] if t],
        }
        return merged
    except Exception:
        logger.debug("Failed to attach Langfuse trace metadata", exc_info=True)
        return config


def new_langfuse_handler():
    """Construct a fresh, non-shared Langfuse CallbackHandler, or None if
    tracing is disabled or construction fails.

    Unlike get_langfuse_handler()'s cached singleton, this is for callers that
    need to read the handler's own `last_trace_id` back afterward (e.g. to link
    to the trace from elsewhere in the app) - sharing the singleton across
    concurrent calls would race, since last_trace_id reflects whichever call
    finished most recently across the whole process, not necessarily this one.
    """
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None

    try:
        from langfuse.langchain import CallbackHandler

        return CallbackHandler()
    except Exception:
        logger.warning("Langfuse handler init failed", exc_info=True)
        return None


def trace_url_for(handler) -> str | None:
    """Return a browser-viewable link to the trace this handler just recorded,
    or None if tracing is disabled, the handler never recorded a trace, or no
    public host is configured to build a link against.
    """
    if handler is None:
        return None
    trace_id = getattr(handler, "last_trace_id", None)
    if not trace_id or not settings.langfuse_public_host:
        return None
    return f"{settings.langfuse_public_host.rstrip('/')}/trace/{trace_id}"
