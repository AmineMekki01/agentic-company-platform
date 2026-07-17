import uuid

from sqlalchemy import ForeignKey, ForeignKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentSkill(Base):
    __tablename__ = "agent_skills"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "agent_slug"],
            ["agent_settings.tenant_id", "agent_settings.slug"],
            ondelete="CASCADE",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_slug: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
    )
    skill_id: Mapped[str] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"),
        primary_key=True,
    )
