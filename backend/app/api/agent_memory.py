"""User-facing view/control over what an agent's conscience has remembered
about the requesting user scoped strictly to their own data.
"""

import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.models.agent_memory import AgentMemory
from app.schemas.chat import AgentMemoryOut
from app.services.memory import delete_memory, get_memories

router = APIRouter(prefix="/agents", tags=["agent-memory"])


@router.get("/{slug}/memory", response_model=list[AgentMemoryOut])
async def list_agent_memories(slug: str, user: CurrentUser, db: DbSession) -> list[AgentMemoryOut]:
    memories = await get_memories(db, user.id, slug, limit=50)
    return [AgentMemoryOut.model_validate(m, from_attributes=True) for m in memories]


@router.delete("/{slug}/memory/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_memory(slug: str, memory_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    memory = await db.get(AgentMemory, memory_id)
    if memory is None or memory.user_id != user.id or memory.agent_slug != slug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")

    await delete_memory(db, str(memory_id))
    await db.commit()
