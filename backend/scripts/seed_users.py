"""Create initial users. Idempotent.

Run once per environment after migrations are applied. Mock data for testing. More to be added.s
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import async_session_factory
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
    session, email: str, password: str, role: UserRole,
    first_name: str | None = None, last_name: str | None = None, occupation: str | None = None,
) -> bool:
    existing = await session.scalar(select(User).where(User.email == email))
    if existing is not None:
        print(f"User {email} already exists - skipping.")
        return False

    session.add(
        User(
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


def _load_json_demo_users() -> list[dict]:
    if not DEMO_JSON.exists():
        return []
    try:
        data = json.loads(DEMO_JSON.read_text(encoding="utf-8"))
        return data.get("users", [])
    except Exception as exc:
        print(f"WARNING: Failed to read {DEMO_JSON}: {exc}")
        return []


async def main() -> None:
    admin_email = _require_env("ADMIN_EMAIL").lower().strip()
    admin_password = _require_env("ADMIN_PASSWORD")

    async with async_session_factory() as session:
        await _create_user(session, admin_email, admin_password, UserRole.ADMIN)

        demo_users = _parse_env_demo_users() or _load_json_demo_users()

        for entry in demo_users:
            role = UserRole.ADMIN if entry.get("role") == "admin" else UserRole.USER
            await _create_user(
                session,
                entry["email"].lower().strip(),
                entry["password"],
                role,
                first_name=entry.get("first_name"),
                last_name=entry.get("last_name"),
                occupation=entry.get("occupation"),
            )


if __name__ == "__main__":
    asyncio.run(main())
