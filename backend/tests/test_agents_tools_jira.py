"""Tests for the IT agent's Jira tools – mocked JiraService, no external calls."""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.tools_jira import create_jira_ticket, get_jira_ticket, get_my_jira_tickets

pytestmark = pytest.mark.asyncio


def _mock_service(project_key="PROJ"):
    service = AsyncMock()
    service.project_key = project_key
    service.base_url = "https://test.atlassian.net"
    return service


async def test_get_my_jira_tickets_no_connector():
    with patch("app.agents.tools_jira.get_first_jira_connector", AsyncMock(return_value=None)):
        result = await get_my_jira_tickets.ainvoke({"user_email": "u@test.com"})
        assert "not configured" in result


async def test_get_my_jira_tickets_no_matching_account():
    service = _mock_service()
    service.find_account_id.return_value = None
    with patch("app.agents.tools_jira.get_first_jira_connector", AsyncMock(return_value=object())), \
         patch("app.agents.tools_jira.get_jira_service_from_connector", AsyncMock(return_value=service)):
        result = await get_my_jira_tickets.ainvoke({"user_email": "u@test.com"})
        assert result == "You have no Jira tickets."
        service.search_issues.assert_not_called()


async def test_get_my_jira_tickets_uses_configured_max_results():
    service = _mock_service()
    service.find_account_id.return_value = "acc-1"
    service.search_issues.return_value = []
    with patch("app.agents.tools_jira.get_first_jira_connector", AsyncMock(return_value=object())), \
         patch("app.agents.tools_jira.get_jira_service_from_connector", AsyncMock(return_value=service)):
        await get_my_jira_tickets.ainvoke({"user_email": "u@test.com", "max_results": 3})
        assert service.search_issues.call_args.kwargs["max_results"] == 3


async def test_get_my_jira_tickets_clamps_max_results():
    service = _mock_service()
    service.find_account_id.return_value = "acc-1"
    service.search_issues.return_value = []
    with patch("app.agents.tools_jira.get_first_jira_connector", AsyncMock(return_value=object())), \
         patch("app.agents.tools_jira.get_jira_service_from_connector", AsyncMock(return_value=service)):
        await get_my_jira_tickets.ainvoke({"user_email": "u@test.com", "max_results": 500})
        assert service.search_issues.call_args.kwargs["max_results"] == 50


async def test_get_my_jira_tickets_empty():
    service = _mock_service()
    service.find_account_id.return_value = "acc-1"
    service.search_issues.return_value = []
    with patch("app.agents.tools_jira.get_first_jira_connector", AsyncMock(return_value=object())), \
         patch("app.agents.tools_jira.get_jira_service_from_connector", AsyncMock(return_value=service)):
        result = await get_my_jira_tickets.ainvoke({"user_email": "u@test.com"})
        assert result == "You have no Jira tickets."


async def test_get_my_jira_tickets_lists_only_reporters_tickets():
    service = _mock_service()
    service.find_account_id.return_value = "acc-1"
    service.search_issues.return_value = [
        {"key": "PROJ-1", "fields": {"summary": "Broken laptop", "status": {"name": "Open"}, "updated": "2026-07-01"}},
    ]
    with patch("app.agents.tools_jira.get_first_jira_connector", AsyncMock(return_value=object())), \
         patch("app.agents.tools_jira.get_jira_service_from_connector", AsyncMock(return_value=service)):
        result = await get_my_jira_tickets.ainvoke({"user_email": "u@test.com"})
        assert "PROJ-1" in result and "Broken laptop" in result and "Open" in result
        service.find_account_id.assert_called_once_with("u@test.com")
        jql = service.search_issues.call_args.args[0]
        assert 'reporter = "acc-1"' in jql


async def test_get_jira_ticket_not_found():
    service = _mock_service()
    service.get_issue.side_effect = ValueError("Jira API error (404)")
    with patch("app.agents.tools_jira.get_first_jira_connector", AsyncMock(return_value=object())), \
         patch("app.agents.tools_jira.get_jira_service_from_connector", AsyncMock(return_value=service)):
        result = await get_jira_ticket.ainvoke({"ticket_key": "PROJ-99", "user_email": "u@test.com"})
        assert result == "Ticket not found."


async def test_get_jira_ticket_wrong_reporter_hidden():
    service = _mock_service()
    service.get_issue.return_value = {
        "fields": {
            "summary": "Someone else's issue",
            "status": {"name": "Open"},
            "reporter": {"emailAddress": "other@test.com"},
        }
    }
    with patch("app.agents.tools_jira.get_first_jira_connector", AsyncMock(return_value=object())), \
         patch("app.agents.tools_jira.get_jira_service_from_connector", AsyncMock(return_value=service)):
        result = await get_jira_ticket.ainvoke({"ticket_key": "PROJ-5", "user_email": "u@test.com"})
        assert result == "Ticket not found."


async def test_get_jira_ticket_own_ticket_with_comments():
    service = _mock_service()
    service.get_issue.return_value = {
        "fields": {
            "summary": "VPN not connecting",
            "status": {"name": "In Progress"},
            "reporter": {"emailAddress": "u@test.com"},
            "description": {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "VPN fails to connect"}]}]},
        }
    }
    service.get_comments.return_value = [
        {"author": {"displayName": "Bob"}, "created": "2026-07-10", "body": {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Looking into it"}]}]}},
    ]
    with patch("app.agents.tools_jira.get_first_jira_connector", AsyncMock(return_value=object())), \
         patch("app.agents.tools_jira.get_jira_service_from_connector", AsyncMock(return_value=service)):
        result = await get_jira_ticket.ainvoke({"ticket_key": "5", "user_email": "u@test.com"})
        assert "PROJ-5" in result  # bare "5" normalized using project_key
        assert "VPN not connecting" in result
        assert "In Progress" in result
        assert "VPN fails to connect" in result
        assert "Bob" in result and "Looking into it" in result


async def test_create_jira_ticket_sets_reporter_from_injected_email():
    service = _mock_service()
    service.create_issue.return_value = {"key": "PROJ-10"}
    with patch("app.agents.tools_jira.get_first_jira_connector", AsyncMock(return_value=object())), \
         patch("app.agents.tools_jira.get_jira_service_from_connector", AsyncMock(return_value=service)):
        result = await create_jira_ticket.ainvoke({
            "summary": "Broken monitor",
            "description": "Screen flickers",
            "issue_type": "Task",
            "user_email": "u@test.com",
        })
        assert "PROJ-10" in result
        assert service.create_issue.call_args.kwargs["reporter_email"] == "u@test.com"


async def test_create_jira_ticket_no_connector():
    with patch("app.agents.tools_jira.get_first_jira_connector", AsyncMock(return_value=None)):
        result = await create_jira_ticket.ainvoke({
            "summary": "x", "description": "y", "issue_type": "Task", "user_email": "u@test.com",
        })
        assert "not configured" in result
