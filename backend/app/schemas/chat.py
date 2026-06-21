import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    """
    Chat request schema.

    This schema represents the chat request data that can be sent
    by clients, including:
    - User content
    - Agent selection
    - Force agent flag
    - Mode selection
    - Linked attachment IDs (uploaded files whose text is injected into context)
    """
    content: str = Field(min_length=1, max_length=8000)
    agent: str | None = None
    force_agent: bool = False
    mode: Literal["auto", "quick", "mid", "deep"] = "auto"
    attachment_ids: list[uuid.UUID] | None = None
    draft: bool = False


class ConversationOut(BaseModel):
    """
    Conversation output schema.
    
    This schema represents the conversation data that can be returned to clients,
    including:
    - Conversation ID
    - Conversation title
    - Optional folder ID
    - Conversation creation timestamp
    - Conversation update timestamp
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    folder_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class AttachmentOut(BaseModel):
    """Attachment output schema for messages."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    mime_type: str | None
    file_size: int
    extracted_text: str | None
    created_at: datetime


class MessageOut(BaseModel):
    """
    Message output schema.

    This schema represents the message data that can be returned to clients,
    including:
    - Message ID
    - Message role
    - Message content
    - Agent ID
    - Citations
    - Attachments
    - Message creation timestamp
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    agent_id: str | None
    citations: list[Any] | None
    tool_calls_log: list[dict[str, Any]] | None = None
    attachments: list[AttachmentOut] = []
    created_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class AgentOut(BaseModel):
    """
    Agent output schema.

    This schema represents the agent data that can be returned to clients,
    including:
    - Agent slug
    - Agent name
    - Agent description
    - Enabled tools
    """
    slug: str
    name: str | None = None
    description: str | None = None
    tools: list[str] | None = None
    allow_uploads: bool = True
    agent_type: str = "standard"


class ChatAttachmentOut(BaseModel):
    """
    Chat attachment output schema.

    Returned after a file is uploaded to a conversation.
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    mime_type: str | None
    file_size: int
    extracted_text: str | None
    created_at: datetime


class JiraTicketDraft(BaseModel):
    """
    Jira ticket draft schema.
    
    This schema represents a draft of a Jira ticket that can be generated
    from conversation context, including:
    - Ticket summary
    - Ticket description
    - Project key
    - Issue type
    """
    summary: str
    description: str
    project_key: str | None = None
    issue_type: str = "Task"


class JiraTicketCreateRequest(BaseModel):
    """
    Jira ticket create request schema.
    
    This schema represents the Jira ticket create request data that can be sent
    by clients, including:
    - Ticket summary
    - Ticket description
    - Project key
    - Issue type
    """
    summary: str
    description: str
    project_key: str | None = None
    issue_type: str = "Task"


class JiraTicketOut(BaseModel):
    """
    Jira ticket output schema.
    
    This schema represents the Jira ticket data that can be returned to clients,
    including:
    - Ticket ID
    - Ticket key
    - Ticket URL
    - Ticket summary
    """
    id: str
    key: str
    url: str
    summary: str


class ConversationFolderOut(BaseModel):
    """Conversation folder output schema."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    color: str | None
    created_at: datetime
    updated_at: datetime


class ConversationFolderCreate(BaseModel):
    """Conversation folder create schema."""
    name: str = Field(min_length=1, max_length=100)
    color: str | None = None


class ConversationFolderUpdate(BaseModel):
    """Conversation folder update schema."""
    name: str | None = Field(default=None, min_length=1, max_length=100)
    color: str | None = None


class MoveToFolderRequest(BaseModel):
    """Request schema to move a conversation to a folder."""
    folder_id: uuid.UUID | None


class MessageFeedbackCreate(BaseModel):
    """Schema for creating feedback on an assistant message."""
    thumbs_up: bool
    comment: str | None = None
    screenshot_attachment_id: uuid.UUID | None = None


class MessageFeedbackOut(BaseModel):
    """Schema for feedback output (admin view with full context)."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    message_id: uuid.UUID
    conversation_id: uuid.UUID
    user_id: uuid.UUID
    agent_id: str
    thumbs_up: bool
    comment: str | None
    screenshot_attachment_id: uuid.UUID | None
    conversation_snapshot: list[dict[str, Any]] | None = None
    tool_calls_log: list[dict[str, Any]] | None = None
    retrieved_sources: list[dict[str, Any]] | None = None
    conversation_actions: list[dict[str, Any]] | None = None
    created_at: datetime


class MessageFeedbackUserOut(BaseModel):
    """Schema for feedback output (user-facing, no snapshots)."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    message_id: uuid.UUID
    thumbs_up: bool
    comment: str | None
    created_at: datetime


class AgentFeedbackSummary(BaseModel):
    """Summary of feedback for an agent."""
    total: int
    thumbs_up: int
    thumbs_down: int
    up_rate_pct: float
