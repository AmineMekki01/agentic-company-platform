"""Tests for Jira service – mocked HTTP to avoid external calls."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.jira import JiraService, adf_to_text, get_jira_service_from_connector

pytestmark = pytest.mark.asyncio


async def test_jira_request_success():
    svc = JiraService("https://test.atlassian.net", "user@test.com", "token")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"key": "PROJ-1"}'
    mock_resp.json.return_value = {"key": "PROJ-1"}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.request = AsyncMock(return_value=mock_resp)

        result = await svc._request("GET", "/issue/PROJ-1")
        assert result == {"key": "PROJ-1"}


async def test_jira_request_error():
    svc = JiraService("https://test.atlassian.net", "user@test.com", "token")
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.text = "Not Found"

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.request = AsyncMock(return_value=mock_resp)

        with pytest.raises(ValueError, match="Jira API error"):
            await svc._request("GET", "/issue/MISSING")


async def test_jira_request_empty_response():
    svc = JiraService("https://test.atlassian.net", "user@test.com", "token")
    mock_resp = MagicMock()
    mock_resp.status_code = 204
    mock_resp.text = ""

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.request = AsyncMock(return_value=mock_resp)

        result = await svc._request("DELETE", "/issue/PROJ-1")
        assert result == {}


async def test_jira_create_issue_no_project_key():
    svc = JiraService("https://test.atlassian.net", "user@test.com", "token")
    with pytest.raises(ValueError, match="project_key is required"):
        await svc.create_issue("summary", "description")


async def test_jira_create_issue_success():
    svc = JiraService("https://test.atlassian.net", "user@test.com", "token", project_key="PROJ")

    createmeta_resp = MagicMock()
    createmeta_resp.status_code = 200
    createmeta_resp.text = '{"projects": [{"issuetypes": [{"name": "Task"}]}]}'
    createmeta_resp.json.return_value = {
        "projects": [{"issuetypes": [{"name": "Task"}]}]
    }

    create_resp = MagicMock()
    create_resp.status_code = 201
    create_resp.text = '{"id": "10001", "key": "PROJ-1", "self": "https://test.atlassian.net/rest/api/3/issue/10001"}'
    create_resp.json.return_value = {"id": "10001", "key": "PROJ-1"}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.request = AsyncMock(side_effect=[createmeta_resp, create_resp])

        result = await svc.create_issue("Test summary", "Test description")
        assert result["key"] == "PROJ-1"
        assert result["id"] == "10001"


async def test_jira_create_issue_with_reporter():
    svc = JiraService("https://test.atlassian.net", "user@test.com", "token", project_key="PROJ")

    createmeta_resp = MagicMock()
    createmeta_resp.status_code = 200
    createmeta_resp.text = '{"projects": [{"issuetypes": [{"name": "Task"}]}]}'
    createmeta_resp.json.return_value = {
        "projects": [{"issuetypes": [{"name": "Task"}]}]
    }

    user_search_resp = MagicMock()
    user_search_resp.status_code = 200
    user_search_resp.text = '[{"accountId": "acc-9", "emailAddress": "reporter@test.com"}]'
    user_search_resp.json.return_value = [{"accountId": "acc-9", "emailAddress": "reporter@test.com"}]

    create_resp = MagicMock()
    create_resp.status_code = 201
    create_resp.text = '{"id": "10002", "key": "PROJ-2"}'
    create_resp.json.return_value = {"id": "10002", "key": "PROJ-2"}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.request = AsyncMock(side_effect=[createmeta_resp, user_search_resp, create_resp])

        result = await svc.create_issue(
            "Bug report", "Something broke", reporter_email="reporter@test.com"
        )
        assert result["key"] == "PROJ-2"

        create_call = mock_client.request.call_args_list[-1]
        payload = create_call.kwargs["json"]
        assert payload["fields"]["reporter"] == {"id": "acc-9"}


async def test_jira_create_issue_reporter_not_found_leaves_unattributed():
    svc = JiraService("https://test.atlassian.net", "user@test.com", "token", project_key="PROJ")

    createmeta_resp = MagicMock()
    createmeta_resp.status_code = 200
    createmeta_resp.text = '{"projects": [{"issuetypes": [{"name": "Task"}]}]}'
    createmeta_resp.json.return_value = {"projects": [{"issuetypes": [{"name": "Task"}]}]}

    user_search_resp = MagicMock()
    user_search_resp.status_code = 200
    user_search_resp.text = "[]"
    user_search_resp.json.return_value = []

    create_resp = MagicMock()
    create_resp.status_code = 201
    create_resp.text = '{"id": "10003", "key": "PROJ-3"}'
    create_resp.json.return_value = {"id": "10003", "key": "PROJ-3"}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.request = AsyncMock(side_effect=[createmeta_resp, user_search_resp, create_resp])

        result = await svc.create_issue(
            "Bug report", "Something broke", reporter_email="nobody@test.com"
        )
        assert result["key"] == "PROJ-3"

        create_call = mock_client.request.call_args_list[-1]
        payload = create_call.kwargs["json"]
        assert "reporter" not in payload["fields"]


async def test_jira_get_issue():
    svc = JiraService("https://test.atlassian.net", "user@test.com", "token")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"key": "PROJ-1", "fields": {"summary": "Test"}}'
    mock_resp.json.return_value = {"key": "PROJ-1", "fields": {"summary": "Test"}}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.request = AsyncMock(return_value=mock_resp)

        result = await svc.get_issue("PROJ-1")
        assert result["key"] == "PROJ-1"


async def test_jira_search_issues():
    svc = JiraService("https://test.atlassian.net", "user@test.com", "token")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"issues": [{"key": "PROJ-1"}, {"key": "PROJ-2"}]}'
    mock_resp.json.return_value = {"issues": [{"key": "PROJ-1"}, {"key": "PROJ-2"}]}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.request = AsyncMock(return_value=mock_resp)

        result = await svc.search_issues('reporter = "user@test.com"')
        assert [i["key"] for i in result] == ["PROJ-1", "PROJ-2"]

        call = mock_client.request.call_args
        assert call.args[0] == "POST"
        assert call.args[1] == "https://test.atlassian.net/rest/api/3/search/jql"
        assert call.kwargs["json"]["jql"] == 'reporter = "user@test.com"'


async def test_jira_search_issues_empty():
    svc = JiraService("https://test.atlassian.net", "user@test.com", "token")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"issues": []}'
    mock_resp.json.return_value = {"issues": []}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.request = AsyncMock(return_value=mock_resp)

        result = await svc.search_issues('reporter = "nobody@test.com"')
        assert result == []


async def test_jira_find_account_id_matches_email():
    svc = JiraService("https://test.atlassian.net", "user@test.com", "token")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '[{"accountId": "acc-1", "emailAddress": "reporter@test.com"}]'
    mock_resp.json.return_value = [{"accountId": "acc-1", "emailAddress": "reporter@test.com"}]

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.request = AsyncMock(return_value=mock_resp)

        result = await svc.find_account_id("reporter@test.com")
        assert result == "acc-1"


async def test_jira_find_account_id_no_match():
    svc = JiraService("https://test.atlassian.net", "user@test.com", "token")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "[]"
    mock_resp.json.return_value = []

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.request = AsyncMock(return_value=mock_resp)

        result = await svc.find_account_id("nobody@test.com")
        assert result is None


async def test_jira_get_comments():
    svc = JiraService("https://test.atlassian.net", "user@test.com", "token")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"comments": [{"author": {"displayName": "Alice"}}]}'
    mock_resp.json.return_value = {"comments": [{"author": {"displayName": "Alice"}}]}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.request = AsyncMock(return_value=mock_resp)

        result = await svc.get_comments("PROJ-1")
        assert result[0]["author"]["displayName"] == "Alice"


def test_adf_to_text_paragraph():
    doc = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Hello world"}]},
        ],
    }
    assert adf_to_text(doc).strip() == "Hello world"


def test_adf_to_text_empty():
    assert adf_to_text(None) == ""
    assert adf_to_text({}) == ""


async def test_get_jira_service_from_connector():
    from cryptography.fernet import Fernet
    from app.core.config import settings
    from app.models import Connector, Secret
    from app.services.secrets import encrypt_credentials

    old_key = settings.fernet_key
    settings.fernet_key = Fernet.generate_key().decode()
    try:
        creds = {"base_url": "https://test.atlassian.net", "email": "u@t.com", "api_token": "tok"}
        secret = Secret(
            slug="jira-secret",
            name="Jira Secret",
            secret_type="jira",
            credentials_encrypted=encrypt_credentials(creds),
        )
        connector = Connector(
            slug="jira-conn",
            name="Jira",
            connector_type="jira",
            secret=secret,
            config={"project_key": "PROJ"},
        )

        svc = await get_jira_service_from_connector(connector)
        assert svc.base_url == "https://test.atlassian.net"
        assert svc.email == "u@t.com"
        assert svc.api_token == "tok"
        assert svc.project_key == "PROJ"
    finally:
        settings.fernet_key = old_key


async def test_get_first_jira_connector_none():
    with patch("app.services.jira.async_session_factory") as mock_sf:
        mock_session = AsyncMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_session.scalars = AsyncMock(return_value=mock_scalars)

        from app.services.jira import get_first_jira_connector
        result = await get_first_jira_connector()
        assert result is None
