"""Jira Service Desk integration for creating tickets from chat."""

import json
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.core.encryption import EncryptionService
from app.db.session import async_session_factory
from app.models import Connector
from sqlalchemy import select

logger = logging.getLogger(__name__)


class JiraService:
    """
    Jira service for creating tickets via REST API.
    
    This service handles the creation of Jira issues/tickets using the Jira REST API.
    It provides methods to create issues with specified summaries, descriptions, and other attributes.
    """
    
    def __init__(self, base_url: str, email: str, api_token: str, project_key: str | None = None):
        """
        Initialize the Jira service.
        
        Args:
            base_url: Jira base URL
            email: Jira account email
            api_token: Jira API
            project_key: Optional default project key
        """
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.api_token = api_token
        self.project_key = project_key
        self._auth = (email, api_token)

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        """
        Make a request to the Jira API.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: API endpoint path
            **kwargs: Additional arguments to pass to the request
            
        Returns:
            Response data as a dictionary
        """
        url = f"{self.base_url}/rest/api/3{path}"
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method, url, auth=self._auth, headers={"Content-Type": "application/json"}, **kwargs
            )
            if resp.status_code >= 400:
                err_detail = resp.text[:1000]
                logger.error("Jira API error: %s %s -> %d: %s", method, path, resp.status_code, err_detail)
                raise ValueError(f"Jira API error ({resp.status_code}): {err_detail}")
            return resp.json() if resp.text else {}

    async def create_issue(
        self,
        summary: str,
        description: str,
        project_key: str | None = None,
        issue_type: str = "Task",
        reporter_email: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a Jira issue.
        
        Args:
            summary: Issue summary/title
            description: Issue description
            project_key: Project key (overrides default if provided)
            issue_type: Issue type name (default: "Task")
            reporter_email: Reporter email (uses configured email if not provided)
            
        Returns:
            Created issue with at least 'id', 'key', 'self' URL
        """
        pk = project_key or self.project_key
        if not pk:
            raise ValueError("project_key is required")

        try:
            meta = await self._request("GET", "/issue/createmeta", params={"projectKeys": pk})
            projects = meta.get("projects", [])
            if not projects:
                raise ValueError(f"Project '{pk}' not found or no create permission")

            available_types: dict[str, dict] = {}
            for it in projects[0].get("issuetypes", []):
                raw_name = it.get("name", "")
                clean = raw_name.lower().replace("[system]", "").strip()
                available_types[clean] = it
            logger.warning("Project %s issue types: %s", pk, list(available_types.keys()))
        except ValueError:
            raise
        except Exception as exc:
            logger.warning("Could not validate project %s: %s", pk, exc)
            available_types = {}

        it_name = issue_type
        clean_key = issue_type.lower().replace("[system]", "").strip()
        if clean_key in available_types:
            it_name = available_types[clean_key].get("name", issue_type)

        payload = {
            "fields": {
                "project": {"key": pk},
                "summary": summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": description}]}
                    ],
                },
                "issuetype": {"name": it_name},
            }
        }
        if reporter_email:
            account_id = await self.find_account_id(reporter_email)
            if account_id:
                payload["fields"]["reporter"] = {"id": account_id}
            else:
                logger.warning("No Jira account found for reporter email %s; issue will be unattributed", reporter_email)

        logger.warning("Jira create payload: %s", json.dumps(payload))
        data = await self._request("POST", "/issue", json=payload)
        logger.info("Created Jira issue %s in project %s", data.get("key"), pk)
        return data

    async def get_issue(self, issue_key: str) -> dict[str, Any]:
        """Fetch an existing Jira issue."""
        return await self._request("GET", f"/issue/{issue_key}")

    async def search_issues(self, jql: str, max_results: int = 20) -> list[dict[str, Any]]:
        """Search issues via JQL, returning the raw issue list.

        Uses /search/jql — Atlassian removed the old /search endpoint (410 Gone).
        """
        data = await self._request(
            "POST",
            "/search/jql",
            json={"jql": jql, "maxResults": max_results, "fields": ["summary", "status", "updated"]},
        )
        logger.info("Jira search_issues jql=%r raw_response_keys=%s", jql, list(data.keys()))
        return data.get("issues", [])

    async def get_comments(self, issue_key: str) -> list[dict[str, Any]]:
        """Fetch comments for an issue, oldest first."""
        data = await self._request("GET", f"/issue/{issue_key}/comment")
        return data.get("comments", [])

    async def find_account_id(self, email: str) -> str | None:
        """Resolve a Jira accountId from an email address.

        JQL `reporter = "<email>"` silently matches nothing on most Jira Cloud
        sites because of privacy settings, even when the email is correct —
        searching must go through accountId instead.
        """
        users = await self._request("GET", "/user/search", params={"query": email})
        if not isinstance(users, list) or not users:
            return None
        for user in users:
            if (user.get("emailAddress") or "").lower() == email.lower():
                return user.get("accountId")
        return users[0].get("accountId")


def adf_to_text(node: dict[str, Any] | None) -> str:
    """Flatten an Atlassian Document Format node into plain text."""
    if not node:
        return ""
    if node.get("type") == "text":
        return node.get("text", "")
    parts = [adf_to_text(child) for child in node.get("content", [])]
    text = " ".join(p for p in parts if p)
    if node.get("type") in ("paragraph", "heading"):
        text += "\n"
    return text


async def get_jira_service_from_connector(connector: Connector) -> JiraService:
    """
    Build a JiraService from a stored Connector row.
    
    Args:
        connector: Connector row from the database
        
    Returns:
        JiraService instance
    """
    crypto = EncryptionService()
    creds_str = crypto.decrypt(connector.credentials_encrypted)
    creds = json.loads(creds_str.replace("'", '"'))
    return JiraService(
        base_url=creds["base_url"],
        email=creds["email"],
        api_token=creds["api_token"],
        project_key=creds.get("project_key"),
    )


async def get_first_jira_connector() -> Connector | None:
    """
    Return the first Jira connector from the DB, if any.
    
    Returns:
        First Jira connector or None if not found
    """
    async with async_session_factory() as session:
        result = await session.scalars(
            select(Connector).where(Connector.connector_type == "jira").limit(1)
        )
        return result.first()
