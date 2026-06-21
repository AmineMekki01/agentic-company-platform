import asyncio
import json
import logging
import uuid
from datetime import datetime

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
from app.services.token_tracker import check_budget as _check_token_budget

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


def _agent_visible(row: AgentSettings, user) -> bool:
    """Return True if the agent is visible to the given user."""
    if user.role == UserRole.ADMIN:
        return True
    if not row.is_published:
        return False

    # beta/staging: if beta_users is set, only beta users + admins can see it
    beta = row.beta_users or []
    if beta:
        return user.email in beta
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
            agent_type=r.agent_type if r.agent_type else "standard",
        )
        for r in rows
        if _agent_visible(r, user)
    ]


def _chunk_text(chunk) -> str:
    """Extract plain text from a message chunk."""
    if isinstance(chunk, dict):
        content = chunk.get("content", "")
        if not content and "data" in chunk and isinstance(chunk["data"], dict):
            content = chunk["data"].get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            )
        return ""

    content = getattr(chunk, "content", None)
    if content is None:
        content = getattr(chunk, "text", None)
    if content is None:
        content = getattr(chunk, "data", None)
        if isinstance(content, dict):
            content = content.get("content", "")
    if content is None:
        content = ""

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    parts.append(part.get("text", ""))
                elif "text" in part:
                    parts.append(part.get("text", ""))
        return "".join(parts)
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

    # entry_agent = what the user selected (conversation owner / routing entry point)
    # agent = who actually handles this turn (may be persisted specialist for direct mode)
    entry_agent = body.agent or default_agent
    agent = entry_agent

    entry_spec = runtime.agent_registry.get(entry_agent)
    is_router_entry = entry_spec is not None and (entry_spec.is_router or entry_spec.is_orchestrator)

    if not body.force_agent and not is_router_entry:
        # Direct specialist chat: allow state persistence across turns
        try:
            config = {"configurable": {"thread_id": str(conversation_id)}}
            existing = await runtime.graph.aget_state(config)
            persisted = existing.values.get("current_agent") if existing else None
            if persisted and persisted in runtime.agent_registry:
                agent = persisted
                logger.info("Direct mode: using persisted agent=%s for conv=%s", agent, conversation_id)
        except Exception:
            pass
    elif is_router_entry:
        logger.info("Router mode: entry=%s for conv=%s", entry_agent, conversation_id)

    agent_row = await db.scalar(select(AgentSettings).where(AgentSettings.slug == agent))
    if user.role != UserRole.ADMIN and agent_row and not _agent_visible(agent_row, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have access to agent '{agent}'",
        )

    # a temporary graph with draft overrides when admin enables draft mode
    graph = runtime.graph
    draft_registry = runtime.agent_registry
    if body.draft and user.role == UserRole.ADMIN and agent_row:
        from app.agents.graph import build_graph
        from app.agents.registry import AgentSpec
        draft = agent_row.draft_config or {}
        system_prompt = draft.get("system_prompt") or agent_row.system_prompt
        model_name = draft.get("llm_model") or agent_row.llm_model
        tools = draft.get("tools") if "tools" in draft else agent_row.tools
        is_orchestrator = draft.get("is_orchestrator") if "is_orchestrator" in draft else agent_row.is_orchestrator
        is_router = draft.get("is_router") if "is_router" in draft else agent_row.is_router
        routes_to = draft.get("routes_to") if "routes_to" in draft else agent_row.routes_to
        connected_sources = draft.get("connected_sources") if "connected_sources" in draft else agent_row.connected_sources
        retrieval_top_k = draft.get("retrieval_top_k") if "retrieval_top_k" in draft else agent_row.retrieval_top_k

        all_agents = await db.scalars(select(AgentSettings))
        registry: dict[str, AgentSpec] = {}
        settings_map: dict[str, dict] = {}
        for a in all_agents.all():
            if a.slug == agent:
                registry[a.slug] = AgentSpec(
                    slug=a.slug,
                    name=draft.get("name") or a.name or a.slug,
                    description=draft.get("description") or a.description or "",
                    system_prompt=system_prompt,
                    default_model=model_name or "gpt-5.4-nano",
                    tools=tools or [],
                    is_orchestrator=bool(is_orchestrator),
                    is_router=bool(is_router),
                    routes_to=routes_to or [],
                    agent_type=draft.get("agent_type") if "agent_type" in draft else (a.agent_type or "standard"),
                    research_config=draft.get("research_config") if "research_config" in draft else a.research_config,
                )
                settings_map[a.slug] = {
                    "model": model_name,
                    "system_prompt": system_prompt,
                    "retrieval_top_k": retrieval_top_k or 5,
                    "connected_sources": connected_sources or [],
                    "agent_type": draft.get("agent_type") if "agent_type" in draft else (a.agent_type or "standard"),
                    "research_config": draft.get("research_config") if "research_config" in draft else a.research_config,
                }
            else:
                registry[a.slug] = AgentSpec(
                    slug=a.slug,
                    name=a.name or a.slug,
                    description=a.description or "",
                    system_prompt=a.system_prompt,
                    default_model=a.llm_model or "gpt-5.4-nano",
                    tools=a.tools or [],
                    is_orchestrator=bool(a.is_orchestrator),
                    is_router=bool(a.is_router) if a.is_router is not None else False,
                    routes_to=a.routes_to or [],
                    agent_type=a.agent_type or "standard",
                    research_config=a.research_config,
                )
                settings_map[a.slug] = {
                    "model": a.llm_model,
                    "system_prompt": a.system_prompt,
                    "retrieval_top_k": a.retrieval_top_k or 5,
                    "connected_sources": a.connected_sources or [],
                    "agent_type": a.agent_type or "standard",
                    "research_config": a.research_config,
                }
        graph = build_graph(checkpointer=None, agent_registry=registry, agent_settings=settings_map)
        draft_registry = registry

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

    logger.warning(
        "Chat request payload conv=%s agent=%s mode=%s content_len=%d content_preview=%s",
        conversation_id,
        agent,
        body.mode,
        len(llm_content),
        llm_content[:500],
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
                "orchestrator_agent": entry_agent,  # sticky to user's selected entry point
                "forced_agent": None,
                "mode": body.mode,
                "step_count": 0,
                "reflection_done": False,
                "_needs_rethink": False,
                "sources": all_sources,
                "source_offset": len(all_sources),
                "user_allowed_slugs": user_allowed_slugs,
                "user_id": str(user.id),
                "conversation_id": str(conversation_id),
            }
            if body.force_agent:
                forced = body.agent or default_agent
                input_state["forced_agent"] = forced
                input_state["current_agent"] = forced
                input_state["orchestrator_agent"] = forced

            logger.warning("Chat stream start conv=%s agent=%s mode=%s draft=%s", conversation_id, agent, body.mode, body.draft)

            budget_exceeded, budget_used, budget_limit = await _check_token_budget(str(user.id), agent)
            if budget_exceeded:
                yield {"event": "budget_warning", "data": json.dumps({
                    "used": budget_used,
                    "limit": budget_limit,
                    "message": f"Monthly budget exceeded (${budget_used:.4f} / ${budget_limit:.4f} USD). Contact an administrator.",
                })}

            assistant_text = ""
            routed_agent = agent
            sources: list[dict] = []
            message_id = str(uuid.uuid4())
            title: str | None = None
            agent_slugs = set(draft_registry.keys())
            tool_calls_log: list[dict] = []

            async for event in graph.astream_events(input_state, config, version="v2"):
                kind = event.get("event")
                name = event.get("name", "")
                tags = event.get("tags") or []

                if kind == "on_chain_start" and name == "router":
                    yield {"event": "step", "data": json.dumps({"step": "routing"})}
                elif kind == "on_chain_start" and name == "tools":
                    yield {"event": "step", "data": json.dumps({"step": "searching"})}
                    tool_input = event.get("data", {}).get("input", {})
                    state_tools = tool_input.get("messages", []) if isinstance(tool_input, dict) else []
                    for msg in state_tools:
                        tc = getattr(msg, "tool_calls", None) if not isinstance(msg, dict) else msg.get("tool_calls")
                        if tc:
                            for t in tc:
                                tool_call_id = t.get("id") if isinstance(t, dict) else getattr(t, "id", None)
                                tool_calls_log.append({
                                    "tool": t.get("name") if isinstance(t, dict) else getattr(t, "name", None),
                                    "args": t.get("args") if isinstance(t, dict) else getattr(t, "args", {}),
                                    "tool_call_id": tool_call_id,
                                    "timestamp": datetime.now().isoformat(),
                                    "status": "started",
                                })
                elif kind == "on_chain_start" and name == "reflect":
                    yield {"event": "step", "data": json.dumps({"step": "verifying"})}
                elif kind in ("on_chain_start", "on_chain_stream") and name in agent_slugs:
                    yield {"event": "step", "data": json.dumps({"step": "thinking"})}
                elif kind == "on_tool_end":
                    data = event.get("data", {})
                    tool_name = event.get("name") or ""
                    tool_input = data.get("input", {}) if isinstance(data, dict) else {}
                    tool_output = data.get("output") if isinstance(data, dict) else None
                    tool_calls_log.append({
                        "tool": tool_name,
                        "args": tool_input,
                        "result": tool_output,
                        "timestamp": datetime.now().isoformat(),
                        "status": "completed",
                    })
                elif kind == "on_chain_end":
                    output = event.get("data", {}).get("output", {})
                    if isinstance(output, dict):
                        if output.get("current_agent"):
                            new_agent = output["current_agent"]
                            if new_agent != routed_agent:
                                routed_agent = new_agent
                                yield {"event": "agent", "data": json.dumps({"agent": routed_agent})}
                        if output.get("sources"):
                            sources = output["sources"]

                        # Capture tool call results at end of tools node
                        if name == "tools":
                            node_messages = output.get("messages", [])
                            for msg in node_messages:
                                msg_type = getattr(msg, "type", None) if not isinstance(msg, dict) else msg.get("type")
                                if msg_type == "tool":
                                    tool_id = getattr(msg, "tool_call_id", None) if not isinstance(msg, dict) else msg.get("tool_call_id")
                                    result = _chunk_text(msg)
                                    if tool_id:
                                        for entry in tool_calls_log:
                                            if entry.get("tool_call_id") == tool_id and entry.get("status") == "started":
                                                entry["result"] = result
                                                entry["status"] = "completed"
                                                break
                                        else:
                                            for entry in tool_calls_log:
                                                if entry.get("status") == "started":
                                                    entry["result"] = result
                                                    entry["tool_call_id"] = tool_id
                                                    entry["status"] = "completed"
                                                    break
                                    else:
                                        for entry in tool_calls_log:
                                            if entry.get("status") == "started":
                                                entry["result"] = result
                                                entry["status"] = "completed"
                                                break

                        if output.get("response_text"):
                            assistant_text = _clean_citations(str(output["response_text"]))
                        if not assistant_text:
                            node_messages = output.get("messages", [])
                            for msg in reversed(node_messages):
                                msg_type = getattr(msg, "type", None) if not isinstance(msg, dict) else msg.get("type")
                                if msg_type in ("ai", "assistant"):
                                    text = _chunk_text(msg)
                                    if text:
                                        assistant_text = _clean_citations(text)
                                        break

            yield {"event": "agent", "data": json.dumps({"agent": routed_agent})}

            if not assistant_text:
                try:
                    final_state = await graph.aget_state(config)
                    final_values = final_state.values if final_state else {}
                except Exception:
                    final_values = {}
                if isinstance(final_values, dict):
                    state_text = final_values.get("response_text")
                    if state_text:
                        assistant_text = _clean_citations(str(state_text))
                        logger.warning(
                            "Captured assistant text from final state conv=%s len=%d preview=%s",
                            conversation_id,
                            len(assistant_text),
                            assistant_text[:500],
                        )
                if not assistant_text:
                    final_messages = final_values.get("messages", []) if isinstance(final_values, dict) else []
                    for m in reversed(final_messages):
                        msg_type = getattr(m, "type", None) if not isinstance(m, dict) else m.get("type")
                        if msg_type in ("ai", "assistant"):
                            text = _chunk_text(m)
                            if text:
                                assistant_text = _clean_citations(text)
                                break

            if assistant_text:
                logger.warning(
                    "Final assistant text conv=%s len=%d preview=%s",
                    conversation_id,
                    len(assistant_text),
                    assistant_text[:1000],
                )
                print(f"[CHAT] assistant_text={assistant_text[:1000]}")
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
                            tool_calls_log=tool_calls_log if tool_calls_log else None,
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
        .order_by(Message.created_at.asc())
    )
    messages = result.all()
    transcript_lines = []
    for m in messages:
        role = "User" if m.role == "user" else "Agent"
        transcript_lines.append(f"{role}: {m.content}")
    transcript = "\n\n".join(transcript_lines)

    from app.agents.llm import get_chat_model
    llm = get_chat_model("gpt-5.4-nano")

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
