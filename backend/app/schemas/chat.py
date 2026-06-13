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
    """
    content: str = Field(min_length=1, max_length=8000)
    agent: str | None = None
    force_agent: bool = False
    mode: Literal["auto", "quick", "mid", "deep"] = "auto"


class ConversationOut(BaseModel):
    """
    Conversation output schema.
    
    This schema represents the conversation data that can be returned to clients,
    including:
    - Conversation ID
    - Conversation title
    - Conversation creation timestamp
    - Conversation update timestamp
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


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
    - Message creation timestamp
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    agent_id: str | None
    citations: list[Any] | None
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
