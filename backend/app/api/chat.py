import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, status
from langchain_core.messages import HumanMessage
from sqlalchemy import func, update
from sse_starlette.sse import EventSourceResponse

from app.agents.runtime import RuntimeDep
from app.api.conversations import get_owned_conversation
from app.api.deps import CurrentUser, DbSession
from app.db.session import async_session_factory
from app.models import AgentSettings, Conversation, Message
from app.schemas.chat import AgentOut, ChatRequest, JiraTicketDraft, JiraTicketCreateRequest, JiraTicketOut
from app.services.jira import get_first_jira_connector, get_jira_service_from_connector
from app.services.titles import generate_title

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@router.get("/agents", response_model=list[AgentOut])
async def list_agents(user: CurrentUser, db: DbSession) -> list[AgentOut]:
    """
    List all available agents.

    Args:
        user: Current authenticated user
        db: Database session

    Returns:
        List of available agents with their details
    """
    from sqlalchemy import select as sa_select
    result = await db.scalars(sa_select(AgentSettings).order_by(AgentSettings.slug))
    rows = result.all()
    return [
        AgentOut(slug=r.slug, name=r.name, description=r.description)
        for r in rows
    ]


def _chunk_text(chunk) -> str:
    """
    Extract plain text from a message chunk (str or content-parts list).
    
    Args:
        chunk: Message chunk to extract text from
        
    Returns:
        Extracted plain text
    """
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return ""


@router.post("/chat/{conversation_id}/stream")
async def chat_stream(
    conversation_id: uuid.UUID,
    body: ChatRequest,
    user: CurrentUser,
    db: DbSession,
    runtime: RuntimeDep,
):
    """
    Stream a chat response for a conversation.
    
    Args:
        conversation_id: UUID of the conversation
        body: Chat request data
        user: Current authenticated user
        db: Database session
        runtime: Agent runtime instance
        
    Returns:
        SSE stream of chat response chunks
        
    Raises:
        HTTPException: If conversation not found or invalid agent
    """
    conversation = await get_owned_conversation(conversation_id, user.id, db)

    registry_keys = list(runtime.agent_registry.keys())
    default_agent = registry_keys[0] if registry_keys else ""
    agent = body.agent or default_agent
    if not agent or agent not in runtime.agent_registry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown agent '{agent}'",
        )

    if not body.force_agent:
        try:
            config = {"configurable": {"thread_id": str(conversation_id)}}
            existing = await runtime.graph.aget_state(config)
            persisted = existing.values.get("current_agent") if existing else None
            if persisted and persisted in runtime.agent_registry:
                agent = persisted
                logger.info("Using persisted agent=%s for conv=%s", agent, conversation_id)
        except Exception:
            pass

    needs_title = conversation.title is None

    db.add(
        Message(
            conversation_id=conversation.id,
            role="user",
            content=body.content,
        )
    )
    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation.id)
        .values(updated_at=func.now())
    )
    await db.commit()

    async def event_generator():
        """
        Generate SSE events for the chat stream.
        
        Yields:
            SSE events with chat response chunks
        """
        collected: list[str] = []
        try:
            config = {"configurable": {"thread_id": str(conversation_id)}}
            input_state = {
                "messages": [HumanMessage(content=body.content)],
                "current_agent": agent,
                "orchestrator_agent": agent,
                "forced_agent": None,
                "mode": body.mode,
            }
            if body.force_agent:
                forced = body.agent or default_agent
                input_state["forced_agent"] = forced
                input_state["current_agent"] = forced
                input_state["orchestrator_agent"] = forced

            logger.warning("Chat stream start conv=%s agent=%s mode=%s", conversation_id, agent, body.mode)
            result = await runtime.graph.ainvoke(input_state, config)
            logger.warning("Graph ainvoke done, result keys=%s", list(result.keys()) if hasattr(result, "keys") else type(result))
            routed_agent = result.get("current_agent", agent)
            yield {"event": "agent", "data": json.dumps({"agent": routed_agent})}
            final_messages = result.get("messages", [])
            logger.warning("Final messages count=%d", len(final_messages))
            if final_messages:
                text = _chunk_text(final_messages[-1])
                logger.warning("Final message text len=%d", len(text))
                if text:
                    collected.append(text)
                    yield {"event": "token", "data": json.dumps({"delta": text})}

            sources = result.get("sources") or []
            if sources:
                yield {"event": "sources", "data": json.dumps({"sources": sources})}

            assistant_text = "".join(collected)
            message_id = str(uuid.uuid4())
            title: str | None = None

            try:
                async with async_session_factory() as session:
                    session.add(
                        Message(
                            id=uuid.UUID(message_id),
                            conversation_id=conversation_id,
                            role="assistant",
                            content=assistant_text,
                            agent_id=routed_agent,
                            citations=sources,
                        )
                    )
                    if needs_title:
                        title = await generate_title(body.content)
                        await session.execute(
                            update(Conversation)
                            .where(Conversation.id == conversation_id)
                            .values(title=title, updated_at=func.now())
                        )
                    else:
                        await session.execute(
                            update(Conversation)
                            .where(Conversation.id == conversation_id)
                            .values(updated_at=func.now())
                        )
                    await session.commit()
                    logger.warning("Message persisted, id=%s", message_id)
            except Exception:
                logger.exception("Persistence failed for conv=%s", conversation_id)

            logger.warning("Streaming done for conv=%s", conversation_id)
            yield {
                "event": "done",
                "data": json.dumps({"message_id": message_id, "title": title}),
            }
        except Exception:
            logger.exception("Chat stream failed for conversation %s", conversation_id)
            yield {
                "event": "error",
                "data": json.dumps(
                    {"detail": "The agent failed to respond. Check backend logs."}
                ),
            }

    return EventSourceResponse(event_generator())


@router.post("/chat/{conversation_id}/actions/jira-draft", response_model=JiraTicketDraft)
async def generate_jira_ticket_draft(
    conversation_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
):
    """
    Generate a Jira ticket draft from the conversation history.
    
    Args:
        conversation_id: UUID of the conversation
        user: Current authenticated user
        db: Database session
        
    Returns:
        JiraTicketDraft with draft data
    """
    conversation = await get_owned_conversation(conversation_id, user.id, db)

    from sqlalchemy import select as sa_select
    result = await db.scalars(
        sa_select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc(), Message.id.asc())
    )
    messages = result.all()
    transcript_lines = []
    for m in messages:
        role = "User" if m.role == "user" else "Agent"
        transcript_lines.append(f"{role}: {m.content}")
    transcript = "\n\n".join(transcript_lines)

    from app.agents.llm import get_chat_model
    llm = get_chat_model("gpt-5-nano")

    prompt = f"""
        Based on the following conversation, generate a Jira ticket summary (title) and description.
        The summary should be a short, clear title (max 80 chars).
        The description should be a detailed but concise explanation of the issue or request, including any relevant context from the conversation.

        Conversation:
        {transcript}

        Return ONLY valid JSON with this exact shape:
        {{"summary": "...", "description": "..."}}
    """
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    text = response.content if hasattr(response, "content") else str(response)

    import re
    json_match = re.search(r'\{{.*?"summary".*?"description".*?\}}', text, re.DOTALL)
    if json_match:
        try:
            draft = json.loads(json_match.group())
        except json.JSONDecodeError:
            draft = {"summary": "Support request", "description": transcript[:2000]}
    else:
        draft = {"summary": "Support request", "description": transcript[:2000]}

    connector = await get_first_jira_connector()
    project_key = None
    if connector:
        from app.core.encryption import EncryptionService
        crypto = EncryptionService()
        creds_str = crypto.decrypt(connector.credentials_encrypted)
        creds = json.loads(creds_str.replace("'", '"'))
        project_key = creds.get("project_key")

    return JiraTicketDraft(
        summary=draft.get("summary", "Support request")[:255],
        description=draft.get("description", "")[:30000],
        project_key=project_key,
        issue_type="Task",
    )


@router.post("/chat/{conversation_id}/actions/jira-create", response_model=JiraTicketOut)
async def create_jira_ticket(
    conversation_id: uuid.UUID,
    body: JiraTicketCreateRequest,
    user: CurrentUser,
    db: DbSession,
):
    """
    Create a Jira issue from an approved draft.
    
    Args:
        conversation_id: UUID of the conversation
        body: Jira ticket creation request data
        user: Current authenticated user
        db: Database session
        
    Returns:
        JiraTicketOut with created ticket data
        
    Raises:
        HTTPException: If no Jira connector is configured
    """
    connector = await get_first_jira_connector()
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No Jira connector configured",
        )

    service = await get_jira_service_from_connector(connector)

    pk = body.project_key
    if not pk:
        from app.core.encryption import EncryptionService
        crypto = EncryptionService()
        creds_str = crypto.decrypt(connector.credentials_encrypted)
        creds = json.loads(creds_str.replace("'", '"'))
        pk = creds.get("project_key")

    if not pk:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project_key is required (not configured in connector)",
        )

    try:
        issue = await service.create_issue(
            summary=body.summary,
            description=body.description,
            project_key=pk,
            issue_type=body.issue_type,
            reporter_email=user.email,
        )
    except ValueError as exc:
        logger.warning("Jira create rejected: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception:
        logger.exception("Failed to create Jira ticket")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to create Jira ticket. Check connector credentials and project key.",
        )

    issue_key = issue.get("key", "unknown")
    issue_id = issue.get("id", "unknown")
    issue_url = f"{service.base_url}/browse/{issue_key}"

    db.add(
        Message(
            conversation_id=conversation_id,
            role="assistant",
            content=f"Created Jira ticket [{issue_key}]({issue_url}): {body.summary}",
            agent_id="system",
        )
    )
    await db.commit()

    return JiraTicketOut(
        id=issue_id,
        key=issue_key,
        url=issue_url,
        summary=body.summary,
    )
