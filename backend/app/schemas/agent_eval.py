import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AgentEvalTestCreate(BaseModel):
    question: str
    expected_answer: str


class AgentEvalTestUpdate(BaseModel):
    question: str | None = None
    expected_answer: str | None = None


class AgentEvalTestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    test_set_id: uuid.UUID
    question: str
    expected_answer: str
    created_at: datetime


class AgentEvalTestSetCreate(BaseModel):
    name: str
    description: str | None = None


class AgentEvalTestSetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class AgentEvalTestSetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    name: str
    description: str | None = None
    created_at: datetime
    created_by: str


class AgentEvalTestSetDetailOut(AgentEvalTestSetOut):
    tests: list[AgentEvalTestOut] = []


class AgentEvalRunCreate(BaseModel):
    name: str
    test_set_ids: list[uuid.UUID]
    thresholds: dict[str, float] = {"answer_correctness": 0.5, "faithfulness": 0.5, "answer_relevancy": 0.5}


class AgentEvalRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    name: str
    status: str
    thresholds: dict[str, float]
    config_source: str = "published"
    agent_version_id: uuid.UUID | None = None
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


class AgentEvalScheduleCreate(BaseModel):
    name: str
    frequency: str
    interval: int = 1
    start_date: datetime
    end_date: datetime | None = None
    test_set_ids: list[uuid.UUID] = []
    thresholds: dict[str, float] = {"answer_correctness": 0.5, "faithfulness": 0.5, "answer_relevancy": 0.5}
    enabled: bool = True


class AgentEvalScheduleUpdate(BaseModel):
    name: str | None = None
    frequency: str | None = None
    interval: int | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    test_set_ids: list[uuid.UUID] | None = None
    thresholds: dict[str, float] | None = None
    enabled: bool | None = None


class AgentEvalScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    name: str
    frequency: str
    interval: int
    start_date: datetime
    end_date: datetime | None = None
    test_set_ids: list[Any] | None = None
    thresholds: dict[str, Any] | None = None
    enabled: bool
    last_triggered_at: datetime | None = None
    created_at: datetime
    created_by: str
