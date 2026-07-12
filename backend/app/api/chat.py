import asyncio
import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, status
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import func, select, update
from sse_starlette.sse import EventSourceResponse

from app.agents.graph import _clean_citations, build_graph
from app.agents.runtime import RuntimeDep
from app.api.conversations import get_owned_conversation
from app.api.deps import CurrentUser, DbSession
from app.db.session import async_session_factory
from app.models import AgentSettings, ChatAttachment, Conversation, Message, UserRole
from app.schemas.chat import AgentOut, ChatRequest, EditMessageRequest, JiraTicketDraft, JiraTicketCreateRequest, JiraTicketOut, RegenerateRequest
from app.services.jira import get_first_jira_connector, get_jira_service_from_connector
from app.core.config import settings as app_settings
from app.core.rate_limit import limiter
from app.core.tracing import new_langfuse_handler, trace_config, trace_url_for
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
            is_router=bool(r.is_router),
            is_orchestrator=bool(r.is_orchestrator),
            memory_enabled=bool(r.memory_enabled),
            emotions_enabled=bool(r.emotions_enabled),
            episodes_enabled=bool(r.episodes_enabled),
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


def _make_stream_response(
    *,
    conversation_id: uuid.UUID,
    agent: str,
    entry_agent: str,
    llm_content: str,
    mode: str,
    force_agent: bool,
    forced_agent_slug: str | None,
    default_agent: str,
    all_sources: list[dict],
    user_allowed_slugs: list[str],
    user_id: uuid.UUID,
    user_email: str,
    graph,
    draft_registry: dict,
    needs_title: bool,
    title_content: str,
    user_message_id: str | None = None,
    input_messages: list | None = None,
) -> EventSourceResponse:
    """Build an SSE EventSourceResponse for agent streaming.

    Shared by chat_stream, regenerate, and edit endpoints.
    When input_messages is provided (edit/regenerate), the LangGraph checkpoint
    is reset so the agent sees a clean history instead of appending to stale state.
    """

    async def event_generator():
        collected: list[str] = []
        try:
            langfuse_handler = new_langfuse_handler()
            config = {"configurable": {"thread_id": str(conversation_id)}}
            config = trace_config(
                config, conversation_id=str(conversation_id), user_id=str(user_id), agent_slug=agent,
                handler=langfuse_handler,
            )

            if input_messages is not None:
                try:
                    await graph.aupdate_state(config, {"messages": []})
                except Exception:
                    logger.warning("Failed to reset checkpoint for conv=%s", conversation_id)

            message_id = str(uuid.uuid4())

            input_state = {
                "messages": input_messages if input_messages is not None else [HumanMessage(content=llm_content)],
                "current_agent": agent,
                "orchestrator_agent": entry_agent,
                "forced_agent": None,
                "mode": mode,
                "step_count": 0,
                "reflection_done": False,
                "_needs_rethink": False,
                "_needs_revision": False,
                "_conscience_revised": False,
                "sources": all_sources,
                "source_offset": len(all_sources),
                "user_allowed_slugs": user_allowed_slugs,
                "user_id": str(user_id),
                "user_email": user_email,
                "conversation_id": str(conversation_id),
                "agent_message_id": message_id,
            }
            if force_agent:
                forced = forced_agent_slug or default_agent
                input_state["forced_agent"] = forced
                input_state["current_agent"] = forced
                input_state["orchestrator_agent"] = forced

            logger.warning("Chat stream start conv=%s agent=%s mode=%s", conversation_id, agent, mode)

            budget_exceeded, budget_used, budget_limit = await _check_token_budget(str(user_id), agent)
            if budget_exceeded:
                yield {"event": "budget_warning", "data": json.dumps({
                    "used": budget_used,
                    "limit": budget_limit,
                    "message": f"Monthly budget exceeded (${budget_used:.4f} / ${budget_limit:.4f} USD). Contact an administrator.",
                })}

            assistant_text = ""
            routed_agent = agent
            sources: list[dict] = []
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
                                new_spec = draft_registry.get(new_agent)
                                old_spec = draft_registry.get(routed_agent)
                                new_is_orchestrator = new_spec and (new_spec.is_router or new_spec.is_orchestrator)
                                old_is_specialist = old_spec and not (old_spec.is_router or old_spec.is_orchestrator)

                                if not (old_is_specialist and new_is_orchestrator):
                                    routed_agent = new_agent
                                    yield {"event": "agent", "data": json.dumps({"agent": routed_agent})}
                        if output.get("sources"):
                            sources = output["sources"]

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
                collected.append(assistant_text)
                yield {"event": "token", "data": json.dumps({"delta": assistant_text})}

            if sources:
                yield {"event": "sources", "data": json.dumps({"sources": sources})}

            logger.warning("Streaming done for conv=%s", conversation_id)
            trace_url = trace_url_for(langfuse_handler)
            done_data: dict = {"message_id": message_id, "title": title}
            if user_message_id:
                done_data["user_message_id"] = user_message_id
            if trace_url:
                done_data["trace_url"] = trace_url
            yield {
                "event": "done",
                "data": json.dumps(done_data),
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
                            trace_url=trace_url,
                        )
                    )
                    if needs_title:
                        title = await generate_title(title_content)
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


@router.post("/chat/{conversation_id}/stream")
@limiter.limit(app_settings.rate_limit_chat)
async def chat_stream(
    request: Request,
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

    if (
        conversation.entry_agent is None
        and not body.force_agent
        and body.agent in runtime.agent_registry
    ):
        conversation.entry_agent = body.agent
        await db.commit()

    entry_agent = conversation.entry_agent or body.agent or default_agent
    if entry_agent not in runtime.agent_registry:
        entry_agent = body.agent or default_agent
    agent = entry_agent

    entry_spec = runtime.agent_registry.get(entry_agent)
    is_router_entry = entry_spec is not None and (entry_spec.is_router or entry_spec.is_orchestrator)
    if is_router_entry:
        logger.info("Router mode: entry=%s for conv=%s", entry_agent, conversation_id)
    else:
        logger.info("Direct mode: entry=%s for conv=%s", entry_agent, conversation_id)

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
        from app.agents.runtime import build_graph_config
        registry, settings_map, workflows = await build_graph_config(db, slug=agent)
        graph = build_graph(checkpointer=None, agent_registry=registry, agent_settings=settings_map, workflows=workflows)
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

    return _make_stream_response(
        conversation_id=conversation_id,
        agent=agent,
        entry_agent=entry_agent,
        llm_content=llm_content,
        mode=body.mode,
        force_agent=body.force_agent,
        forced_agent_slug=body.agent,
        default_agent=default_agent,
        all_sources=all_sources,
        user_allowed_slugs=user_allowed_slugs,
        user_id=user.id,
        user_email=user.email,
        graph=graph,
        draft_registry=draft_registry,
        needs_title=needs_title,
        title_content=body.content,
        user_message_id=str(msg.id),
    )


@router.post("/chat/{conversation_id}/regenerate")
@limiter.limit(app_settings.rate_limit_actions)
async def regenerate_response(
    request: Request,
    conversation_id: uuid.UUID,
    body: RegenerateRequest,
    user: CurrentUser,
    db: DbSession,
    runtime: RuntimeDep,
):
    """
    Regenerate the last assistant response.

    Truncates all messages after the last user message, then re-runs the agent
    on that user message to produce a fresh assistant response.

    Args:
        conversation_id: UUID of the conversation
        body: Regenerate request data (mode)
        user: Current authenticated user
        db: Database session
        runtime: Agent runtime instance

    Returns:
        SSE stream of chat response chunks

    Raises:
        HTTPException: If conversation not found or no user message to regenerate from
    """
    conversation = await get_owned_conversation(conversation_id, user.id, db)

    msgs_result = await db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
    )
    all_messages = msgs_result.all()

    last_user_idx = None
    for i in range(len(all_messages) - 1, -1, -1):
        if all_messages[i].role == "user":
            last_user_idx = i
            break

    if last_user_idx is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No user message found to regenerate from",
        )

    last_user_msg = all_messages[last_user_idx]

    msgs_to_delete = all_messages[last_user_idx + 1:]
    if msgs_to_delete:
        for m in msgs_to_delete:
            await db.delete(m)
        await db.commit()

    registry_keys = list(runtime.agent_registry.keys())
    default_agent = registry_keys[0] if registry_keys else ""

    answering_agent = None
    for m in msgs_to_delete:
        if m.role == "assistant" and m.agent_id:
            answering_agent = m.agent_id
            break

    prev_agent = None
    for i in range(last_user_idx - 1, -1, -1):
        if all_messages[i].role == "assistant" and all_messages[i].agent_id:
            prev_agent = all_messages[i].agent_id
            break

    entry_from_conv = conversation.entry_agent if conversation.entry_agent in runtime.agent_registry else None
    agent = entry_from_conv or answering_agent or prev_agent or default_agent
    if not agent or agent not in runtime.agent_registry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown agent '{agent}'",
        )

    entry_agent = agent
    agent_row = await db.scalar(select(AgentSettings).where(AgentSettings.slug == agent))
    if user.role != UserRole.ADMIN and agent_row and not _agent_visible(agent_row, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have access to agent '{agent}'",
        )

    result = await db.execute(select(AgentSettings))
    user_allowed_slugs = [
        row.slug for row in result.scalars().all() if _agent_visible(row, user)
    ]

    needs_title = conversation.title is None

    history_messages = []
    for m in all_messages[:last_user_idx + 1]:
        if m.role == "user":
            history_messages.append(HumanMessage(content=m.content))
        elif m.role == "assistant":
            history_messages.append(AIMessage(content=m.content))

    return _make_stream_response(
        conversation_id=conversation_id,
        agent=agent,
        entry_agent=entry_agent,
        llm_content=last_user_msg.content,
        mode=body.mode,
        force_agent=False,
        forced_agent_slug=None,
        default_agent=default_agent,
        all_sources=[],
        user_allowed_slugs=user_allowed_slugs,
        user_id=user.id,
        user_email=user.email,
        graph=runtime.graph,
        draft_registry=runtime.agent_registry,
        needs_title=needs_title,
        title_content=last_user_msg.content,
        input_messages=history_messages,
    )


@router.post("/chat/{conversation_id}/messages/{message_id}/edit")
@limiter.limit(app_settings.rate_limit_actions)
async def edit_message(
    request: Request,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    body: EditMessageRequest,
    user: CurrentUser,
    db: DbSession,
    runtime: RuntimeDep,
):
    """
    Edit a user message and resubmit.

    Updates the content of the specified user message, truncates all messages
    after it, then re-runs the agent to produce a fresh assistant response.

    Args:
        conversation_id: UUID of the conversation
        message_id: UUID of the user message to edit
        body: Edit request data (new content + mode)
        user: Current authenticated user
        db: Database session
        runtime: Agent runtime instance

    Returns:
        SSE stream of chat response chunks

    Raises:
        HTTPException: If conversation/message not found, or message is not a user message
    """
    conversation = await get_owned_conversation(conversation_id, user.id, db)

    target_msg = await db.get(Message, message_id)
    if target_msg is None or target_msg.conversation_id != conversation.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )
    if target_msg.role != "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only edit user messages",
        )

    target_msg.content = body.content
    await db.commit()

    msgs_result = await db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
    )
    all_messages = msgs_result.all()

    target_idx = None
    for i, m in enumerate(all_messages):
        if m.id == message_id:
            target_idx = i
            break

    msgs_to_delete = all_messages[target_idx + 1:] if target_idx is not None else []
    if msgs_to_delete:
        for m in msgs_to_delete:
            await db.delete(m)
        await db.commit()

    registry_keys = list(runtime.agent_registry.keys())
    default_agent = registry_keys[0] if registry_keys else ""

    answering_agent = None
    for m in msgs_to_delete:
        if m.role == "assistant" and m.agent_id:
            answering_agent = m.agent_id
            break

    prev_agent = None
    for i in range(target_idx - 1, -1, -1):
        if all_messages[i].role == "assistant" and all_messages[i].agent_id:
            prev_agent = all_messages[i].agent_id
            break

    entry_from_conv = conversation.entry_agent if conversation.entry_agent in runtime.agent_registry else None
    agent = entry_from_conv or answering_agent or prev_agent or default_agent
    if not agent or agent not in runtime.agent_registry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown agent '{agent}'",
        )

    entry_agent = agent
    agent_row = await db.scalar(select(AgentSettings).where(AgentSettings.slug == agent))
    if user.role != UserRole.ADMIN and agent_row and not _agent_visible(agent_row, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have access to agent '{agent}'",
        )

    result = await db.execute(select(AgentSettings))
    user_allowed_slugs = [
        row.slug for row in result.scalars().all() if _agent_visible(row, user)
    ]

    needs_title = conversation.title is None

    history_messages = []
    for m in all_messages[:target_idx + 1]:
        if m.role == "user":
            history_messages.append(HumanMessage(content=m.content))
        elif m.role == "assistant":
            history_messages.append(AIMessage(content=m.content))

    return _make_stream_response(
        conversation_id=conversation_id,
        agent=agent,
        entry_agent=entry_agent,
        llm_content=body.content,
        mode=body.mode,
        force_agent=False,
        forced_agent_slug=None,
        default_agent=default_agent,
        all_sources=[],
        user_allowed_slugs=user_allowed_slugs,
        user_id=user.id,
        user_email=user.email,
        graph=runtime.graph,
        draft_registry=runtime.agent_registry,
        needs_title=needs_title,
        title_content=body.content,
        input_messages=history_messages,
    )


@router.post("/chat/{conversation_id}/actions/jira-draft", response_model=JiraTicketDraft)
@limiter.limit(app_settings.rate_limit_actions)
async def generate_jira_ticket_draft(
    request: Request,
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
@limiter.limit(app_settings.rate_limit_actions)
async def create_jira_ticket(
    request: Request,
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
