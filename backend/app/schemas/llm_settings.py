from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

TracingMode = Literal["full", "masked", "off"]


class LLMSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ollama_enabled: bool
    ollama_base_url: str
    ollama_enabled_models: list[str]
    tracing_mode: TracingMode = "full"


class LLMSettingsUpdate(BaseModel):
    ollama_enabled: bool = False
    ollama_base_url: str = Field(default="http://ollama:11434/v1", max_length=500)
    ollama_enabled_models: list[str] = Field(default_factory=list)
    tracing_mode: TracingMode = "full"


class OllamaModelInfo(BaseModel):
    name: str
    size: str | None = None
    quantization: str | None = None


class OllamaTestResult(BaseModel):
    connected: bool
    models: list[OllamaModelInfo] = []
    error: str | None = None
