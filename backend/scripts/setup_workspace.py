import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.encryption import EncryptionService
from app.db.session import async_session_factory
from app.models import AgentSettings, Connector, KnowledgeSource


AGENTS: list[dict] = [
    {
        "slug": "it",
        "name": "IT Support",
        "description": (
            "IT support specialist for troubleshooting, software, hardware, access requests, "
            "VPN, email, and technical runbooks. Can create Jira tickets for issues that need escalation."
        ),
        "llm_model": "gpt-5.4-nano",
        "system_prompt": """
            You are the IT Support Specialist. You help employees with technical issues based strictly on the company's IT documentation and connected knowledge sources.

            Rules:
            - Only answer IT-related topics: software, hardware, VPN, email, access, passwords, troubleshooting steps, and technical runbooks.
            - If the question is not IT-related, politely decline and suggest the General Assistant or HR Specialist agent.
            - Before answering, verify the retrieved context actually contains the specific information requested. If the context only mentions general policies but not the user's exact question (e.g., a specific team name, model, or person), say so honestly.
            - Cite the exact document and section when providing answers.
            - Use numbered citations like [1], [2] that map to the Sources list. NEVER repeat the same citation twice in a row.
            - If the answer is not found in the retrieved context, say so honestly and suggest creating a Jira ticket for further help.
            - If the user reports a bug or issue that needs IT team follow-up, offer to create a Jira ticket using the create_jira_ticket tool.
            - Be technical but accessible. Avoid jargon when possible.
        """,
        "tools": ["create_jira_ticket"],
        "is_orchestrator": False,
        "routes_to": [],
        "visibility": "restricted",
        "knowledge_source_slug": "it-helpdesk-documents",
    },
    {
        "slug": "hr",
        "name": "HR Specialist",
        "description": (
            "Human Resources specialist for company policies, benefits, leave requests, payroll, "
            "onboarding, offboarding, and employee relations. Only answers from HR-connected knowledge sources."
        ),
        "llm_model": "gpt-5.4-nano",
        "system_prompt": """
            You are the HR Specialist. You answer questions strictly based on the company's HR policy documents and connected knowledge sources.

            Rules:
            - Only answer HR-related topics: policies, benefits, leave, payroll, onboarding, offboarding, code of conduct, and disciplinary procedures.
            - If the question is not HR-related, politely decline and suggest the General Assistant or IT Support agent.
            - Cite the exact policy document and section when providing answers.
            - Use numbered citations like [1], [2] that map to the Sources list.
            - If the answer is not found in the retrieved context, say so honestly and suggest contacting HR directly.
            - Be professional, clear, and respectful.
        """,
        "tools": [],
        "is_orchestrator": False,
        "routes_to": [],
        "visibility": "restricted",
        "knowledge_source_slug": "hr-documents",
    },
    {
        "slug": "finance",
        "name": "Finance Assistant",
        "description": (
            "An internal AI agent dedicated to managing and auditing Tbibi App's corporate finance, "
            "expense policies, and local tax compliance. It acts as an instant digital financial controller for the team."
        ),
        "llm_model": "gpt-5.4-nano",
        "system_prompt": """
            You are the expert AI Finance Assistant for the company Tbibi App. Your primary purpose is to act as an internal corporate auditor, accountant, and strategic financial guide. You provide precise, policy-compliant answers to employees, department heads, and executives using the company's verified financial registries, procurement policies, and tax compliance documents.

            ## 2. Core Operational Principles
            *   **Absolute Numerical Accuracy:** Financial data must be calculated and delivered with perfect precision. Never round numbers unless explicitly requested, and always include the currency (MAD) where appropriate.
            *   **Strict Policy Enforcement:** You are the gatekeeper of company policy. If an employee's request or expense report violates corporate daily caps, procurement authorization thresholds, or compliance protocols, you must firmly flag the violation and state the policy rule.
            *   **No Hallucinations / "I Don't Know" Policy:** You must answer questions *only* using the facts and data provided in your knowledge base vector database. If the data required to answer a question is missing, say: "I cannot find this information in the corporate financial records. Please consult the Finance Team directly." Never invent account numbers, balances, names, or metrics.
            *   **Localized Context Awareness:** You understand Moroccan fiscal parameters (e.g., CGI, TVA, IGR, CNSS, and CNDP regulations). Treat deadlines (like the 10th-of-the-month tax cutoffs) with the highest priority.

            ## 3. Communication Style
            *   **Tone:** Professional, objective, analytical, and supportive yet mathematically uncompromising.
            *   **Structure:** Break down complex multi-part queries into clean, scannable layouts using bolding, lists, and tables. Highlight warnings or policy rejections clearly.

            ### RULES
            - Use numbered citations like [1], [2] that map to the Sources list.
        """,
        "tools": [],
        "is_orchestrator": False,
        "routes_to": [],
        "visibility": "restricted",
        "knowledge_source_slug": "finance-documents",
    },
    {
        "slug": "general",
        "name": "General Assistant",
        "description": (
            "Company-wide assistant. Handles general questions, explains company services, "
            "and routes to specialist agents when the topic is clearly outside general knowledge."
        ),
        "llm_model": "gpt-5.4-nano",
        "system_prompt": """
            You are the General Assistant - the central orchestrator of this multi-agent system.
            Your primary job is to understand the user's question and either answer it yourself
            or route it to the most appropriate specialist agent.

            ## Routing Rules
            1. If the user explicitly mentions an agent with @slug, route to that agent immediately.
            2. If the query clearly belongs to one specialist domain, route to that specialist.
            3. If the query is broad, cross-domain, ambiguous, or a simple greeting, answer it yourself.
            4. If the query is a follow-up in an ongoing specialist conversation, stay with that specialist.
            5. Never make up information outside your knowledge base or retrieved context.

            ## When to Handle vs Route
            - Handle directly: general knowledge, greetings, small talk, clarifying questions...
            - Route to specialist: domain-specific policy, procedure, or action.

            ## Tone
            Be helpful, concise, and professional. If you route, acknowledge the hand-off briefly.
        """,
        "tools": [],
        "is_orchestrator": True,
        "routes_to": ["it", "hr", "finance"],
        "visibility": "restricted",
        "knowledge_source_slug": "",
    },
]


def _get_env(var: str, default: str | None = None) -> str | None:
    return os.environ.get(var, default)


def _require_env(var: str) -> str:
    value = _get_env(var)
    if not value:
        print(f"ERROR: {var} environment variable is required.", file=sys.stderr)
        sys.exit(1)
    return value


async def _ensure_s3_connector(session) -> Connector:
    slug = _get_env("S3_CONNECTOR_SLUG", "s3-connector")
    name = _get_env("S3_CONNECTOR_NAME", "s3-connector")

    existing = await session.scalar(select(Connector).where(Connector.slug == slug))
    if existing:
        print(f"S3 connector '{slug}' already exists - skipping.")
        return existing

    access_key = _require_env("AWS_ACCESS_KEY")
    secret_key = _require_env("AWS_SECRET_KEY")
    region = _get_env("AWS_REGION")
    endpoint_url = _get_env("AWS_ENDPOINT_URL")

    creds = {
        "access_key": access_key,
        "secret_key": secret_key,
        "region": region,
    }
    if endpoint_url:
        creds["endpoint_url"] = endpoint_url

    crypto = EncryptionService()
    encrypted = crypto.encrypt(json.dumps(creds))

    connector = Connector(
        slug=slug,
        name=name,
        connector_type="s3",
        credentials_encrypted=encrypted,
    )
    session.add(connector)
    await session.commit()
    await session.refresh(connector)
    print(f"Created S3 connector: {slug}")
    return connector


async def _ensure_knowledge_source(session, connector: Connector, slug: str, name: str, prefix: str) -> KnowledgeSource:
    existing = await session.scalar(select(KnowledgeSource).where(KnowledgeSource.slug == slug))
    if existing:
        print(f"Knowledge source '{slug}' already exists - skipping.")
        return existing

    bucket = _get_env("S3_BUCKET_NAME", "agentic-platform-app")

    ks = KnowledgeSource(
        slug=slug,
        name=name,
        source_type="s3",
        config={"bucket": bucket, "prefix": prefix},
        connector_id=connector.id,
        status="pending",
        chunk_count=0,
    )
    session.add(ks)
    await session.commit()
    await session.refresh(ks)
    print(f"Created knowledge source: {slug} (s3://{bucket}/{prefix})")
    return ks


async def _ensure_agent(session, agent_def: dict, source_id: str | None) -> None:
    slug = agent_def["slug"]
    created_by = (agent_def.get("created_by") or _get_env("SEED_USER_EMAIL", "seed@system.local") or "seed@system.local").strip().lower()
    allowed_users = agent_def.get("allowed_users")
    if allowed_users is None and agent_def.get("visibility") == "restricted":
        allowed_users = [created_by]

    existing = await session.scalar(select(AgentSettings).where(AgentSettings.slug == slug))
    if existing:
        existing.system_prompt = agent_def["system_prompt"]
        existing.visibility = agent_def.get("visibility", existing.visibility)
        existing.created_by = created_by
        existing.allowed_users = allowed_users
        await session.commit()
        print(f"Agent '{slug}' already exists - updated settings (owner={created_by}, visibility={existing.visibility}).")
        return

    connected_sources = [source_id] if source_id else []

    row = AgentSettings(
        slug=slug,
        name=agent_def["name"],
        description=agent_def["description"],
        llm_model=agent_def.get("llm_model", "gpt-5.4-nano"),
        system_prompt=agent_def["system_prompt"],
        retrieval_enabled=bool(connected_sources),
        connected_sources=connected_sources,
        tools=agent_def.get("tools", []),
        is_orchestrator=agent_def.get("is_orchestrator", False),
        routes_to=agent_def.get("routes_to") or None,
        visibility=agent_def.get("visibility", "all"),
        created_by=created_by,
        allowed_users=allowed_users,
    )
    session.add(row)
    await session.commit()
    print(
        f"Created agent: {slug} (owner={created_by}, visibility={row.visibility}) -> linked to source '{source_id or 'none'}'"
    )


async def main() -> None:
    async with async_session_factory() as session:
        connector = await _ensure_s3_connector(session)

        sources_map: dict[str, KnowledgeSource] = {}
        source_configs = [
            ("it-helpdesk-documents", "it-helpdesk-documents", "it-helpdesk-documents/"),
            ("hr-documents", "hr-documents", "hr-documents/"),
            ("finance-documents", "finance-documents", "finance-documents/"),
        ]
        for slug, name, prefix in source_configs:
            ks = await _ensure_knowledge_source(session, connector, slug, name, prefix)
            sources_map[slug] = ks

        for agent_def in AGENTS:
            ks_slug = agent_def.get("knowledge_source_slug")
            source_id = str(sources_map[ks_slug].id) if ks_slug and ks_slug in sources_map else None
            await _ensure_agent(session, agent_def, source_id)

    print("\nWorkspace setup complete.")
    print("TIP: Trigger a sync for each knowledge source from the Admin UI or API.")


if __name__ == "__main__":
    asyncio.run(main())
