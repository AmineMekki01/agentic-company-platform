"""Row-Level Security definitions, shared by migration and the test fixture."""
from collections.abc import Callable

RLS_TABLES = [
    "users", "agent_settings", "agent_versions", "agent_workflows", "agent_skills",
    "skills", "agent_memories", "agent_emotion_states", "agent_episodes",
    "agent_eval_tests", "agent_eval_test_sets", "agent_eval_runs", "agent_eval_results",
    "agent_eval_schedules", "conversations", "conversation_folders", "messages",
    "chat_attachments", "message_feedback", "feedback_attachments", "connectors",
    "secrets", "knowledge_sources", "token_usage", "token_budgets", "upload_settings",
    "llm_settings",
]

_PREDICATE = "tenant_id = current_setting('app.tenant_id', true)::uuid"


def apply_statements() -> list[str]:
    """Ordered SQL to create the app_rls role and enable RLS + policies."""
    stmts = [
        "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='app_rls') "
        "THEN CREATE ROLE app_rls NOLOGIN; END IF; END $$;",
        "GRANT app_rls TO CURRENT_USER;",
        "GRANT USAGE ON SCHEMA public TO app_rls;",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_rls;",
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_rls;",
    ]
    for t in RLS_TABLES:
        stmts.append(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;")
        stmts.append(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY;")
        stmts.append(
            f"CREATE POLICY tenant_isolation ON {t} "
            f"USING ({_PREDICATE}) WITH CHECK ({_PREDICATE});"
        )
    return stmts


def remove_statements() -> list[str]:
    """Ordered SQL to reverse apply_statements (migration downgrade)."""
    stmts: list[str] = []
    for t in RLS_TABLES:
        stmts.append(f"DROP POLICY IF EXISTS tenant_isolation ON {t};")
        stmts.append(f"ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY;")
        stmts.append(f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;")
    stmts.append(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM app_rls;"
    )
    stmts.append("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM app_rls;")
    stmts.append("REVOKE USAGE ON SCHEMA public FROM app_rls;")
    stmts.append("REVOKE app_rls FROM CURRENT_USER;")
    stmts.append("DROP ROLE IF EXISTS app_rls;")
    return stmts


def apply_rls(execute: Callable[[str], object]) -> None:
    for stmt in apply_statements():
        execute(stmt)


def remove_rls(execute: Callable[[str], object]) -> None:
    for stmt in remove_statements():
        execute(stmt)
