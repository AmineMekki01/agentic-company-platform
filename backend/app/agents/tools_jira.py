"""Jira tools for the IT agent: create tickets and look up existing ones."""

import logging
import re
from typing import Annotated

from langchain_core.tools import InjectedToolArg, tool

from app.services.jira import adf_to_text, get_first_jira_connector, get_jira_service_from_connector

logger = logging.getLogger(__name__)


async def _get_service_and_project():
    """Return (service, project_key) from the configured connector, or (None, None)."""
    connector = await get_first_jira_connector()
    if connector is None:
        return None, None
    service = await get_jira_service_from_connector(connector)
    return service, service.project_key


def _normalize_ticket_key(ticket_key: str, project_key: str | None) -> str:
    ticket_key = ticket_key.strip().upper()
    if re.fullmatch(r"\d+", ticket_key) and project_key:
        return f"{project_key}-{ticket_key}"
    return ticket_key


def _escape_jql_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


@tool
async def create_jira_ticket(
    summary: Annotated[str, "Short ticket title"],
    description: Annotated[str, "Detailed description of the issue"],
    issue_type: Annotated[str, "Issue type: Bug, Task, or Story"] = "Task",
    user_email: Annotated[str | None, InjectedToolArg] = None,
) -> str:
    """
    Create a Jira support ticket, reported by the current user.

    Use this when the user reports an IT issue that should be tracked formally
    (hardware failure, access requests, bugs).

    Returns:
        Success message with ticket key and URL
    """
    service, project_key = await _get_service_and_project()
    if service is None:
        return "Jira is not configured (no Jira connector set up)."
    if not project_key:
        return "Jira is not configured (no project_key set on the Jira connector)."

    try:
        issue = await service.create_issue(
            summary=summary,
            description=description,
            project_key=project_key,
            issue_type=issue_type,
            reporter_email=user_email,
        )
        ticket_key = issue.get("key", "unknown")
        return f"Ticket created successfully: {ticket_key}\nURL: {service.base_url}/browse/{ticket_key}"
    except Exception as exc:
        logger.exception("Jira ticket creation failed")
        return f"Failed to create Jira ticket: {exc}"


@tool
async def get_my_jira_tickets(
    user_email: Annotated[str | None, InjectedToolArg] = None,
    max_results: Annotated[int, InjectedToolArg] = 20,
) -> str:
    """
    List the current user's own Jira tickets (most recently updated first).

    Use this when the user asks to see their tickets, e.g. "get me all my tickets".
    """
    if not user_email:
        return "Could not determine your account email."

    service, _ = await _get_service_and_project()
    if service is None:
        return "Jira is not configured (no Jira connector set up)."

    try:
        account_id = await service.find_account_id(user_email)
    except Exception:
        logger.exception("Jira account lookup failed for %s", user_email)
        account_id = None
    logger.info("get_my_jira_tickets: user_email=%s resolved account_id=%s", user_email, account_id)
    if not account_id:
        return "You have no Jira tickets."

    max_results = max(1, min(max_results or 20, 50))
    jql = f'reporter = "{_escape_jql_string(account_id)}" ORDER BY updated DESC'
    try:
        issues = await service.search_issues(jql, max_results=max_results)
    except Exception as exc:
        logger.exception("Jira ticket search failed, jql=%r", jql)
        return f"Failed to fetch your Jira tickets: {exc}"

    logger.info("get_my_jira_tickets: jql=%r returned %d issue(s)", jql, len(issues))
    if not issues:
        return "You have no Jira tickets."

    lines = []
    for issue in issues:
        fields = issue.get("fields", {})
        key = issue.get("key", "unknown")
        summary = fields.get("summary", "")
        status = fields.get("status", {}).get("name", "unknown")
        updated = fields.get("updated", "")
        lines.append(f"{key} — {summary} [{status}] (updated: {updated})")
    return "\n".join(lines)


@tool
async def get_jira_ticket(
    ticket_key: Annotated[str, "Ticket number, e.g. 'IT-42' or just '42'"],
    user_email: Annotated[str | None, InjectedToolArg] = None,
) -> str:
    """
    Get the status, description, and recent comments for one of the current user's own tickets.

    Use this when the user asks about a specific ticket by number, its status, or its comments.
    """
    if not user_email:
        return "Could not determine your account email."

    service, project_key = await _get_service_and_project()
    if service is None:
        return "Jira is not configured (no Jira connector set up)."

    normalized_key = _normalize_ticket_key(ticket_key, project_key)

    try:
        issue = await service.get_issue(normalized_key)
    except Exception:
        return "Ticket not found."

    fields = issue.get("fields", {})
    reporter_email = (fields.get("reporter") or {}).get("emailAddress", "")
    if reporter_email.lower() != user_email.lower():
        return "Ticket not found."

    summary = fields.get("summary", "")
    status = fields.get("status", {}).get("name", "unknown")
    description = adf_to_text(fields.get("description")).strip()

    try:
        comments = await service.get_comments(normalized_key)
    except Exception:
        comments = []

    lines = [f"{normalized_key} — {summary} [{status}]"]
    if description:
        lines.append(f"\nDescription:\n{description}")

    if comments:
        lines.append("\nRecent comments:")
        for comment in comments[-5:]:
            author = (comment.get("author") or {}).get("displayName", "unknown")
            created = comment.get("created", "")
            body = adf_to_text(comment.get("body")).strip()
            lines.append(f"- {author} ({created}): {body}")

    return "\n".join(lines)
