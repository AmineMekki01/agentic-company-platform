import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AgentEvalTestCreate(BaseModel):
    name: str
    question: str
    expected_answer: str


class AgentEvalTestUpdate(BaseModel):
    name: str | None = None
    question: str | None = None
    expected_answer: str | None = None


class AgentEvalTestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    name: str
    question: str
    expected_answer: str
    created_at: datetime
    created_by: str


class AgentEvalRunCreate(BaseModel):
    name: str
    test_ids: list[uuid.UUID]
    # Per-metric thresholds, e.g. {"answer_correctness": 0.6, "faithfulness": 0.5}
    thresholds: dict[str, float] = {"answer_correctness": 0.5, "faithfulness": 0.5, "answer_relevancy": 0.5}


class AgentEvalRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    name: str
    status: str
    thresholds: dict[str, float]
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    created_by: str
    pass_count: int = 0
    fail_count: int = 0
    total_tests: int = 0


class AgentEvalResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    test_id: uuid.UUID
    test_name: str = ""
    actual_answer: str | None = None
    retrieved_contexts: list[str] | None = None
    metrics: dict[str, Any] | None = None
    metric_passes: dict[str, bool] | None = None
    score: float | None = None
    passed: bool | None = None
    duration_ms: int | None = None
    created_at: datetime


class AgentEvalRunDetailOut(AgentEvalRunOut):
    results: list[AgentEvalResultOut] = []
