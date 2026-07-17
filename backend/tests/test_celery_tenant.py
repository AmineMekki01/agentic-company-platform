import uuid


def test_tenant_task_sets_context():
    from app.celery_app import celery_app
    from app.tasks.base import TenantTask
    from app.core.tenant_context import get_current_tenant

    seen = {}

    @celery_app.task(base=TenantTask, bind=True, name="test.probe_ctx")
    def _probe(self, tenant_id=None):
        seen["tid"] = get_current_tenant()

    tid = uuid.uuid4()
    _probe(tenant_id=str(tid))
    assert seen["tid"] == tid


def test_tenant_task_without_id_runs():
    from app.celery_app import celery_app
    from app.tasks.base import TenantTask

    @celery_app.task(base=TenantTask, bind=True, name="test.probe_noid")
    def _probe(self, **kwargs):
        return "ok"

    assert _probe() == "ok"


def test_task_modules_import():
    import app.tasks.memory_maintenance as mm
    import app.tasks.retention as ret
    import app.tasks.eval_tasks as ev

    assert hasattr(mm, "decay_stale_memories_for_tenant")
    assert hasattr(ret, "purge_expired_attachments_for_tenant")
    assert hasattr(ev, "process_eval_schedules_for_tenant")


def test_batch_queue_routing():
    from app.celery_app import celery_app
    routes = celery_app.conf.task_routes
    assert routes["app.tasks.eval_tasks.*"]["queue"] == "batch"
    assert celery_app.conf.task_default_queue == "interactive"


def test_tenant_task_applies_tenant_runtime(monkeypatch):
    """A background job must run with its tenant's trace policy AND LLM endpoint,
    not another tenant's and not a process-global."""
    from app.agents.llm import get_ollama_base_url
    from app.celery_app import celery_app
    from app.core.tenant_settings_cache import TenantRuntime
    from app.core.tracing import get_tracing_mode
    from app.tasks.base import TenantTask

    monkeypatch.setattr(
        "app.tasks.base._load_tenant_runtime",
        lambda tid: TenantRuntime(
            tracing_mode="off",
            ollama_enabled=True,
            ollama_base_url="http://acme-ollama:11434/v1",
        ),
    )
    seen = {}

    @celery_app.task(base=TenantTask, bind=True, name="test.probe_runtime")
    def _probe(self, tenant_id=None):
        seen["mode"] = get_tracing_mode()
        seen["ollama"] = get_ollama_base_url()

    _probe(tenant_id=str(uuid.uuid4()))
    assert seen["mode"] == "off"
    assert seen["ollama"] == "http://acme-ollama:11434/v1"
    assert get_tracing_mode() == "full"
    assert get_ollama_base_url() != "http://acme-ollama:11434/v1"


def test_tenant_task_tolerates_runtime_lookup_failure(monkeypatch):
    from app.celery_app import celery_app
    from app.core.tracing import get_tracing_mode
    from app.tasks.base import TenantTask

    monkeypatch.setattr("app.tasks.base._load_tenant_runtime", lambda tid: None)
    seen = {}

    @celery_app.task(base=TenantTask, bind=True, name="test.probe_runtime_fail")
    def _probe(self, tenant_id=None):
        seen["mode"] = get_tracing_mode()

    _probe(tenant_id=str(uuid.uuid4()))
    assert seen["mode"] == "full"
