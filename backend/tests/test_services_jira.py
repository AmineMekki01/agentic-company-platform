"""Tests for Jira service – mocked HTTP to avoid external calls."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.jira import JiraService, get_jira_service_from_connector

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

    create_resp = MagicMock()
    create_resp.status_code = 201
    create_resp.text = '{"id": "10002", "key": "PROJ-2"}'
    create_resp.json.return_value = {"id": "10002", "key": "PROJ-2"}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.request = AsyncMock(side_effect=[createmeta_resp, create_resp])

        result = await svc.create_issue(
            "Bug report", "Something broke", reporter_email="reporter@test.com"
        )
        assert result["key"] == "PROJ-2"


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


async def test_get_jira_service_from_connector():
    from cryptography.fernet import Fernet
    from app.core.config import settings
    from app.core.encryption import EncryptionService
    from app.models import Connector

    old_key = settings.fernet_key
    settings.fernet_key = Fernet.generate_key().decode()
    try:
        crypto = EncryptionService()
        creds = {"base_url": "https://test.atlassian.net", "email": "u@t.com", "api_token": "tok", "project_key": "PROJ"}
        encrypted = crypto.encrypt(json.dumps(creds))

        connector = Connector(
            slug="jira-conn",
            name="Jira",
            connector_type="jira",
            credentials_encrypted=encrypted,
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
