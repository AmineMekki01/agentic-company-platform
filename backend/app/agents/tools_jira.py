"""Jira tool for IT agent to create support tickets."""

import logging
from typing import Annotated

from langchain_core.tools import tool

from app.core.config import settings

logger = logging.getLogger(__name__)


@tool
async def create_jira_ticket(
    summary: Annotated[str, "Short ticket title"],
    description: Annotated[str, "Detailed description of the issue"],
    issue_type: Annotated[str, "Issue type: Bug, Task, or Story"] = "Task",
) -> str:
    """
    Create a Jira support ticket.
    
    Use this when the user reports an IT issue that should be tracked formally
    (hardware failure, access requests, bugs).
    
    Args:
        summary: Short ticket title
        description: Detailed description of the issue
        issue_type: Issue type: Bug, Task, or Story (default: Task)
        
    Returns:
        Success message with ticket key and URL
    """
    if not all([settings.jira_base_url, settings.jira_email, settings.jira_api_token]):
        return "Jira is not configured (missing JIRA_BASE_URL, JIRA_EMAIL, or JIRA_API_TOKEN)."

    import httpx

    url = f"{settings.jira_base_url.rstrip('/')}/rest/api/2/issue"
    auth = (settings.jira_email, settings.jira_api_token)
    payload = {
        "fields": {
            "project": {"key": settings.jira_project_key or "IT"},
            "summary": summary,
            "description": description,
            "issuetype": {"name": issue_type},
        }
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, auth=auth, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            ticket_key = data.get("key", "unknown")
            return f"Ticket created successfully: {ticket_key}\nURL: {settings.jira_base_url}/browse/{ticket_key}"
    except Exception as exc:
        logger.exception("Jira ticket creation failed")
        return f"Failed to create Jira ticket: {exc}"
