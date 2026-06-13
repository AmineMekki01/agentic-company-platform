from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.runtime import AgentRuntime
from app.api.admin_agents import router as admin_agents_router
from app.api.admin_users import router as admin_users_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.connector_browse import router as connector_browse_router
from app.api.connector_credentials import router as connector_credentials_router
from app.api.conversations import router as conversations_router
from app.api.health import router as health_router
from app.api.knowledge_sources import router as knowledge_sources_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.services.rag import RAGService

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle."""
    runtime = AgentRuntime()
    try:
        await runtime.startup()
        logger.info("Agent runtime started")
    except Exception:
        logger.exception("Agent runtime failed to start - chat endpoints will 503")
    app.state.runtime = runtime

    rag = RAGService()
    try:
        await rag.ensure_collection()
        logger.info("RAG collection ready")
    except Exception:
        logger.exception("RAG collection init failed")
    app.state.rag = rag

    yield
    await runtime.shutdown()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(conversations_router, prefix="/api")
    app.include_router(chat_router, prefix="/api")
    app.include_router(admin_agents_router, prefix="/api")
    app.include_router(admin_users_router, prefix="/api")
    app.include_router(knowledge_sources_router, prefix="/api")
    app.include_router(connector_credentials_router, prefix="/api")
    app.include_router(connector_browse_router, prefix="/api")

    return app


app = create_app()
