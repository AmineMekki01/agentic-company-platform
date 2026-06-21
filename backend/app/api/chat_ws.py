"""WebSocket chat endpoint for deep research agents.

Supports bidirectional communication for:
- Streaming progress events (planning, searching, compressing, writing report)
- Interactive clarification (agent asks question, user responds, research resumes)
"""

import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select, update

from app.agents.deep_research import DeepResearchConfig, run_deep_research
from app.agents.runtime import AgentRuntime
from app.db.session import async_session_factory
from app.models import AgentSettings, Conversation, Message, UserRole
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat-ws"])


async def _authenticate_ws(websocket: WebSocket) -> User | None:
    """Authenticate a WebSocket connection via query param token."""
    token = websocket.query_params.get("token")
    if not token:
        return None
    try:
        from app.core.security import decode_access_token
        import jwt
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload["sub"])
    except Exception:
        return None

    from app.db.session import async_session_factory
    async with async_session_factory() as session:
        user = await session.get(User, user_id)
        return user


def _agent_visible(row: AgentSettings, user: User) -> bool:
    """Check if agent is visible to user (same logic as chat.py)."""
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


@router.websocket("/ws/chat/{conversation_id}")
async def chat_ws(websocket: WebSocket, conversation_id: uuid.UUID):
    """WebSocket endpoint for deep research chat.

    Protocol:
        Client → Server:
            {"type": "message", "content": "...", "agent": "deep_research", "mode": "auto"}
            {"type": "clarification_response", "content": "user's answer"}

        Server → Client:
            {"type": "step", "step": "clarifying|planning|searching|compressing|writing_report", "detail": "..."}
            {"type": "clarification", "question": "..."}
            {"type": "token", "delta": "final report text"}
            {"type": "sources", "sources": [...]}
            {"type": "done", "message_id": "..."}
            {"type": "error", "detail": "..."}
    """
    user = await _authenticate_ws(websocket)
    if user is None:
        await websocket.close(code=4001, reason="Not authenticated")
        return

    await websocket.accept()

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")

            if msg_type == "message":
                await _handle_message(websocket, data, user, conversation_id)
            elif msg_type == "clarification_response":
                await _handle_clarification_response(websocket, data, user, conversation_id)
            else:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "detail": f"Unknown message type: {msg_type}",
                }))
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for conv=%s", conversation_id)
    except Exception as e:
        logger.exception("WebSocket error for conv=%s", conversation_id)
        try:
            await websocket.send_text(json.dumps({"type": "error", "detail": str(e)}))
        except Exception:
            pass


async def _handle_message(
    websocket: WebSocket,
    data: dict,
    user: User,
    conversation_id: uuid.UUID,
):
    """Handle a new user message - start deep research."""
    content = data.get("content", "")
    agent_slug = data.get("agent", "")
    mode = data.get("mode", "auto")

    if not content or not agent_slug:
        await websocket.send_text(json.dumps({
            "type": "error",
            "detail": "Missing 'content' or 'agent' field",
        }))
        return

    async with async_session_factory() as db:
        # Verify conversation ownership
        conv = await db.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user.id,
            )
        )
        if conv is None:
            await websocket.send_text(json.dumps({
                "type": "error",
                "detail": "Conversation not found",
            }))
            return

        agent_row = await db.scalar(
            select(AgentSettings).where(AgentSettings.slug == agent_slug)
        )
        if agent_row is None:
            await websocket.send_text(json.dumps({
                "type": "error",
                "detail": f"Agent '{agent_slug}' not found",
            }))
            return

        if not _agent_visible(agent_row, user):
            await websocket.send_text(json.dumps({
                "type": "error",
                "detail": f"You do not have access to agent '{agent_slug}'",
            }))
            return

        if agent_row.agent_type != "deep_research":
            await websocket.send_text(json.dumps({
                "type": "error",
                "detail": "WebSocket chat is only for deep research agents. Use the SSE endpoint for standard agents.",
            }))
            return

        msg = Message(
            conversation_id=conversation_id,
            role="user",
            content=content,
        )
        db.add(msg)
        await db.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=func.now())
        )
        await db.commit()
        await db.refresh(msg)

        research_config_dict = agent_row.research_config or {}

        if agent_row.connected_sources and not research_config_dict.get("connected_sources"):
            research_config_dict["connected_sources"] = agent_row.connected_sources
        dr_config = DeepResearchConfig.from_dict(research_config_dict)

        from app.main import app
        runtime: AgentRuntime | None = getattr(app.state, "runtime", None)
        checkpointer = runtime.checkpointer if runtime else None

        thread_id = f"{conversation_id}:{agent_slug}:research"

        report_text = ""
        clarification_needed = False

        async for event in run_deep_research(
            user_message=content,
            config=dr_config,
            thread_id=thread_id,
            checkpointer=checkpointer,
        ):
            evt_type = event.get("type")

            if evt_type == "clarification":
                clarification_needed = True

                question = event.get("question", "")
                ai_msg = Message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=question,
                    agent_id=agent_slug,
                )
                db.add(ai_msg)
                await db.commit()

                await websocket.send_text(json.dumps({
                    "type": "clarification",
                    "question": question,
                }))
                break

            elif evt_type == "progress":
                await websocket.send_text(json.dumps({
                    "type": "step",
                    "step": event.get("step", ""),
                    "detail": event.get("detail", ""),
                }))

            elif evt_type == "report":
                report_text = event.get("content", "")

            elif evt_type == "error":
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "detail": event.get("detail", "Unknown error"),
                }))
                return

        if clarification_needed:
            return

        if report_text:
            ai_msg = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=report_text,
                agent_id=agent_slug,
            )
            db.add(ai_msg)
            await db.commit()
            await db.refresh(ai_msg)

            if conv.title is None:
                try:
                    from app.services.titles import generate_title
                    title = await generate_title(content)
                    if title:
                        await db.execute(
                            update(Conversation)
                            .where(Conversation.id == conversation_id)
                            .values(title=title)
                        )
                        await db.commit()
                except Exception:
                    logger.exception("Title generation failed")

            await websocket.send_text(json.dumps({
                "type": "token",
                "delta": report_text,
            }))

        await websocket.send_text(json.dumps({
            "type": "done",
            "message_id": str(uuid.uuid4()),
        }))


async def _handle_clarification_response(
    websocket: WebSocket,
    data: dict,
    user: User,
    conversation_id: uuid.UUID,
):
    """Handle user's clarification response - resume deep research."""
    answer = data.get("content", "")
    agent_slug = data.get("agent", "")

    if not answer:
        await websocket.send_text(json.dumps({
            "type": "error",
            "detail": "Missing 'content' in clarification response",
        }))
        return

    async with async_session_factory() as db:
        # Save user's clarification answer
        msg = Message(
            conversation_id=conversation_id,
            role="user",
            content=answer,
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)

        agent_row = await db.scalar(
            select(AgentSettings).where(AgentSettings.slug == agent_slug)
        )
        if agent_row is None:
            await websocket.send_text(json.dumps({
                "type": "error",
                "detail": f"Agent '{agent_slug}' not found",
            }))
            return

        from sqlalchemy import select as sa_select, desc
        user_msgs = await db.scalars(
            sa_select(Message)
            .where(Message.conversation_id == conversation_id)
            .where(Message.role == "user")
            .order_by(desc(Message.created_at))
            .limit(2)
        )
        msg_list = user_msgs.all()
        original_user_message = ""
        if len(msg_list) >= 2:
            original_user_message = msg_list[1].content
        elif len(msg_list) == 1:
            original_user_message = msg_list[0].content

        research_config_dict = agent_row.research_config or {}
        if agent_row.connected_sources and not research_config_dict.get("connected_sources"):
            research_config_dict["connected_sources"] = agent_row.connected_sources
        dr_config = DeepResearchConfig.from_dict(research_config_dict)

        from app.main import app
        runtime: AgentRuntime | None = getattr(app.state, "runtime", None)
        checkpointer = runtime.checkpointer if runtime else None

        thread_id = f"{conversation_id}:{agent_slug}:research"

        report_text = ""
        async for event in run_deep_research(
            user_message=original_user_message,
            config=dr_config,
            thread_id=thread_id,
            checkpointer=checkpointer,
            resume_answer=answer,
        ):
            evt_type = event.get("type")

            if evt_type == "progress":
                await websocket.send_text(json.dumps({
                    "type": "step",
                    "step": event.get("step", ""),
                    "detail": event.get("detail", ""),
                }))
            elif evt_type == "report":
                report_text = event.get("content", "")
            elif evt_type == "error":
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "detail": event.get("detail", "Unknown error"),
                }))
                return

        if report_text:
            ai_msg = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=report_text,
                agent_id=agent_slug,
            )
            db.add(ai_msg)
            await db.commit()
            await db.refresh(ai_msg)

            await websocket.send_text(json.dumps({
                "type": "token",
                "delta": report_text,
            }))

        await websocket.send_text(json.dumps({
            "type": "done",
            "message_id": str(uuid.uuid4()),
        }))
