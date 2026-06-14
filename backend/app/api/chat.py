import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, status
from langchain_core.messages import HumanMessage
from sqlalchemy import func, select, update
from sse_starlette.sse import EventSourceResponse

from app.agents.graph import _clean_citations
from app.agents.runtime import RuntimeDep
from app.api.conversations import get_owned_conversation
from app.api.deps import CurrentUser, DbSession
from app.db.session import async_session_factory
from app.models import AgentSettings, ChatAttachment, Conversation, Message, UserRole
from app.schemas.chat import AgentOut, ChatRequest, JiraTicketDraft, JiraTicketCreateRequest, JiraTicketOut
from app.services.jira import get_first_jira_connector, get_jira_service_from_connector
from app.services.titles import generate_title

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


def _agent_visible(row: AgentSettings, user) -> bool:
    """Return True if the agent is visible to the given user."""
    if user.role == UserRole.ADMIN:
        return True
    if row.visibility == "all":
        return True
    if row.visibility == "admin_only":
        return False
    if row.visibility == "restricted":
        allowed = row.allowed_users or []
        return user.email in allowed
    return False


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
        AgentOut(
            slug=r.slug,
            name=r.name,
            description=r.description,
            tools=r.tools or [],
            allow_uploads=r.allow_uploads,
        )
        for r in rows
        if _agent_visible(r, user)
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

    agent_row = await db.scalar(select(AgentSettings).where(AgentSettings.slug == agent))
    if user.role != UserRole.ADMIN and agent_row and not _agent_visible(agent_row, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have access to agent '{agent}'",
        )

    if body.attachment_ids and agent_row and not agent_row.allow_uploads:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"File uploads are disabled for agent '{agent}'",
        )

    needs_title = conversation.title is None

    result = await db.execute(select(AgentSettings))
    user_allowed_slugs = [
        row.slug for row in result.scalars().all() if _agent_visible(row, user)
    ]

    msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=body.content,
    )
    db.add(msg)
    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation.id)
        .values(updated_at=func.now())
    )
    await db.commit()
    await db.refresh(msg)

    if body.attachment_ids:
        await db.execute(
            update(ChatAttachment)
            .where(ChatAttachment.id.in_(body.attachment_ids))
            .values(message_id=msg.id)
        )
        await db.commit()

    all_attachments_result = await db.execute(
        select(ChatAttachment).where(
            ChatAttachment.conversation_id == conversation.id
        ).order_by(ChatAttachment.created_at.asc())
    )
    all_attachments = all_attachments_result.scalars().all()

    all_sources: list[dict] = []
    for i, att in enumerate(all_attachments, start=1):
        all_sources.append({
            "rank": i,
            "title": att.filename,
            "id": str(att.id),
            "url": None,
        })

    llm_content = body.content
    if body.attachment_ids:
        new_attachments = [att for att in all_attachments if att.id in body.attachment_ids]
        file_blocks = []
        for i, att in enumerate(new_attachments, start=1):
            header = f"[{i}] {att.filename}"
            if att.extracted_text:
                file_blocks.append(f"{header}\n{att.extracted_text}")
            else:
                file_blocks.append(f"{header}\n(No text extracted)")
        if file_blocks:
            docs_section = "\n\n---\n\n".join(file_blocks)
            llm_content = (
                f"The user uploaded the following document(s).\n\n"
                f"{docs_section}\n\n"
                f"---\n\n"
                f"User question: {body.content}"
            )

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
                "messages": [HumanMessage(content=llm_content)],
                "current_agent": agent,
                "orchestrator_agent": agent,
                "forced_agent": None,
                "mode": body.mode,
                "step_count": 0,
                "reflection_done": False,
                "_needs_rethink": False,
                "sources": all_sources,
                "source_offset": len(all_sources),
                "user_allowed_slugs": user_allowed_slugs,
            }
            if body.force_agent:
                forced = body.agent or default_agent
                input_state["forced_agent"] = forced
                input_state["current_agent"] = forced
                input_state["orchestrator_agent"] = forced

            logger.warning("Chat stream start conv=%s agent=%s mode=%s", conversation_id, agent, body.mode)

            assistant_text = ""
            routed_agent = agent
            sources: list[dict] = []
            message_id = str(uuid.uuid4())
            title: str | None = None
            agent_slugs = set(runtime.agent_registry.keys())

            async for event in runtime.graph.astream_events(input_state, config, version="v2"):
                kind = event.get("event")
                name = event.get("name", "")
                tags = event.get("tags") or []

                if kind == "on_chain_start" and name == "router":
                    yield {"event": "step", "data": json.dumps({"step": "routing"})}
                elif kind == "on_chain_start" and name == "tools":
                    yield {"event": "step", "data": json.dumps({"step": "searching"})}
                elif kind == "on_chain_start" and name == "reflect":
                    yield {"event": "step", "data": json.dumps({"step": "verifying"})}
                elif kind in ("on_chain_start", "on_chain_stream") and name in agent_slugs:
                    yield {"event": "step", "data": json.dumps({"step": "thinking"})}
                elif kind == "on_chain_end":
                    output = event.get("data", {}).get("output", {})
                    if isinstance(output, dict):
                        if output.get("current_agent"):
                            routed_agent = output["current_agent"]
                        if output.get("sources"):
                            sources = output["sources"]

            yield {"event": "agent", "data": json.dumps({"agent": routed_agent})}

            final_state = await runtime.graph.aget_state(config)
            final_messages = final_state.values.get("messages", []) if final_state else []

            for m in reversed(final_messages):
                if getattr(m, "type", None) in ("ai", "assistant"):
                    text = _chunk_text(m)
                    if text:
                        assistant_text = _clean_citations(text)
                        break

            if assistant_text:
                logger.warning("Final assistant text len=%d", len(assistant_text))
                collected.append(assistant_text)
                yield {"event": "token", "data": json.dumps({"delta": assistant_text})}

            if sources:
                yield {"event": "sources", "data": json.dumps({"sources": sources})}

            logger.warning("Streaming done for conv=%s", conversation_id)
            yield {
                "event": "done",
                "data": json.dumps({"message_id": message_id, "title": title}),
            }

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
                        yield {
                            "event": "title",
                            "data": json.dumps({"title": title}),
                        }
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
