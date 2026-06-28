from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentSkill(Base):
    __tablename__ = "agent_skills"

    agent_slug: Mapped[str] = mapped_column(
        ForeignKey("agent_settings.slug", ondelete="CASCADE"),
        primary_key=True,
    )
    skill_id: Mapped[str] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"),
        primary_key=True,
    )
