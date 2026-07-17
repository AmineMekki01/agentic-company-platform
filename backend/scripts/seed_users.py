"""Create initial users. Idempotent.

Run once per environment after migrations are applied. Mock data for testing. More to be added.s
"""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uuid

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.core.tenant_context import set_current_tenant
from app.db.session import async_session_factory
from app.models.llm_settings import LLMSettings
from app.models.tenant import Tenant
from app.models.user import User, UserRole

SCRIPT_DIR = Path(__file__).resolve().parent
DEMO_JSON = SCRIPT_DIR / "demo_users.json"


def _require_env(var: str) -> str:
    value = os.environ.get(var)
    if not value:
        print(f"ERROR: {var} environment variable is required.", file=sys.stderr)
        sys.exit(1)
    return value


async def _create_user(
    session, tenant_id: uuid.UUID, email: str, password: str, role: UserRole,
    first_name: str | None = None, last_name: str | None = None, occupation: str | None = None,
) -> bool:
    existing = await session.scalar(
        select(User).where(User.tenant_id == tenant_id, User.email == email)
    )
    if existing is not None:
        print(f"User {email} already exists in tenant {tenant_id} - skipping.")
        return False

    session.add(
        User(
            tenant_id=tenant_id,
            email=email,
            password_hash=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            occupation=occupation,
            role=role,
        )
    )
    await session.commit()
    print(f"Created {role.value} user: {email}")
    return True


def _parse_env_demo_users() -> list[dict]:
    raw = os.environ.get("DEMO_USERS", "")
    users = []
    if not raw:
        return users
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if ":" not in pair:
            print(f"WARNING: Invalid DEMO_USERS entry '{pair}' (expected email:password)")
            continue
        email, password = pair.split(":", 1)
        users.append({"email": email.strip().lower(), "password": password.strip(), "role": "user"})
    return users


def _load_json_demo_data() -> dict:
    if not DEMO_JSON.exists():
        return {}
    try:
        return json.loads(DEMO_JSON.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"WARNING: Failed to read {DEMO_JSON}: {exc}")
        return {}


async def _ensure_tenant(session, entry: dict, index: int) -> uuid.UUID:
    slug = entry["slug"].strip().lower()
    tenant_id = (
        uuid.UUID(settings.default_tenant_id)
        if entry.get("default") or index == 0
        else uuid.uuid5(uuid.NAMESPACE_URL, f"agentic-company-platform:{slug}")
    )
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        tenant = Tenant(
            id=tenant_id,
            slug=slug,
            name=entry["name"].strip(),
            status=entry.get("status", "active"),
        )
        session.add(tenant)
        await session.commit()
        print(f"Created tenant {tenant.name}: {tenant_id}")
    else:
        tenant.slug = slug
        tenant.name = entry["name"].strip()
        tenant.status = entry.get("status", "active")

    llm_config = entry.get("llm_settings", {})
    tenant_settings = await session.scalar(
        select(LLMSettings).where(LLMSettings.tenant_id == tenant_id)
    )
    if tenant_settings is None:
        tenant_settings = LLMSettings(tenant_id=tenant_id)
        session.add(tenant_settings)
    tenant_settings.ollama_enabled = llm_config.get("ollama_enabled", False)
    tenant_settings.ollama_base_url = llm_config.get(
        "ollama_base_url", "http://ollama:11434/v1"
    )
    tenant_settings.ollama_enabled_models = llm_config.get("ollama_enabled_models", [])
    await session.commit()
    print(f"Configured tenant: {tenant.name} ({slug})")
    return tenant_id


async def main() -> None:
    admin_email = _require_env("ADMIN_EMAIL").lower().strip()
    admin_password = _require_env("ADMIN_PASSWORD")
    demo_data = _load_json_demo_data()
    tenant_entries = demo_data.get("tenants", [])
    if not tenant_entries:
        tenant_entries = [{"slug": "default", "name": "Default", "default": True}]

    async with async_session_factory() as session:
        for index, tenant_entry in enumerate(tenant_entries):
            tenant_id = await _ensure_tenant(session, tenant_entry, index)
            set_current_tenant(tenant_id)

            demo_users = tenant_entry.get("users", [])
            if index == 0:
                await _create_user(
                    session, tenant_id, admin_email, admin_password, UserRole.ADMIN
                )
                demo_users = _parse_env_demo_users() or demo_users or demo_data.get("users", [])

            for entry in demo_users:
                role = UserRole.ADMIN if entry.get("role") == "admin" else UserRole.USER
                await _create_user(
                    session,
                    tenant_id,
                    entry["email"].lower().strip(),
                    entry["password"],
                    role,
                    first_name=entry.get("first_name"),
                    last_name=entry.get("last_name"),
                    occupation=entry.get("occupation"),
                )


if __name__ == "__main__":
    asyncio.run(main())
