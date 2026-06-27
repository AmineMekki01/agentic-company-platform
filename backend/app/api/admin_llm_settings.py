"""Admin LLM settings API."""

import httpx
from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import AdminUser, DbSession
from app.core.config import settings as app_settings
from app.models import LLMSettings
from app.schemas.llm_settings import (
    LLMSettingsOut,
    LLMSettingsUpdate,
    OllamaModelInfo,
    OllamaTestResult,
)

router = APIRouter(prefix="/admin/llm-settings", tags=["admin"])


async def _get_or_create(db: DbSession) -> LLMSettings:
    row = await db.scalar(select(LLMSettings))
    if row is None:
        row = LLMSettings(
            ollama_enabled=app_settings.ollama_enabled,
            ollama_base_url=app_settings.ollama_base_url,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


def _sync_to_runtime(row: LLMSettings) -> None:
    app_settings.ollama_enabled = row.ollama_enabled
    app_settings.ollama_base_url = row.ollama_base_url


@router.get("", response_model=LLMSettingsOut)
async def get_llm_settings(user: AdminUser, db: DbSession) -> LLMSettingsOut:
    row = await _get_or_create(db)
    return LLMSettingsOut.model_validate(row)


@router.put("", response_model=LLMSettingsOut)
async def update_llm_settings(
    user: AdminUser,
    db: DbSession,
    body: LLMSettingsUpdate,
) -> LLMSettingsOut:
    row = await _get_or_create(db)
    row.ollama_enabled = body.ollama_enabled
    row.ollama_base_url = body.ollama_base_url
    row.ollama_enabled_models = body.ollama_enabled_models
    await db.commit()
    await db.refresh(row)
    _sync_to_runtime(row)
    return LLMSettingsOut.model_validate(row)


@router.post("/ollama/test", response_model=OllamaTestResult)
async def test_ollama_connection(user: AdminUser, base_url: str = "") -> OllamaTestResult:
    url = base_url or app_settings.ollama_base_url
    base = url.rstrip("/v1").rstrip("/")
    tags_url = f"{base}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(tags_url)
            resp.raise_for_status()
            data = resp.json()
            models = []
            for m in data.get("models", []):
                name = m.get("model", "")
                if not name:
                    continue
                size_bytes = m.get("size", 0)
                if size_bytes:
                    if size_bytes >= 1_000_000_000:
                        size_str = f"{size_bytes / 1_000_000_000:.1f} GB"
                    elif size_bytes >= 1_000_000:
                        size_str = f"{size_bytes / 1_000_000:.0f} MB"
                    else:
                        size_str = f"{size_bytes / 1_000:.0f} KB"
                else:
                    size_str = None
                details = m.get("details", {})
                quant = details.get("quantization_level")
                models.append(OllamaModelInfo(name=name, size=size_str, quantization=quant))
            return OllamaTestResult(connected=True, models=models)
    except Exception as exc:
        return OllamaTestResult(connected=False, error=str(exc))
