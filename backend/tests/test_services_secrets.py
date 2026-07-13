"""Tests for app.services.secrets: credential encryption and connector resolution."""

import pytest
from cryptography.fernet import Fernet

from app.core.config import settings
from app.models.connector import Connector
from app.models.secret import Secret
from app.services.secrets import (
    decrypt_credentials,
    encrypt_credentials,
    get_connector_credentials,
    get_connector_credentials_encrypted,
)


@pytest.fixture(autouse=True)
def _fernet_key(monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())


def test_encrypt_decrypt_round_trip():
    creds = {"api_token": "it's a token with an apostrophe", "base_url": "https://x.atlassian.net"}
    encrypted = encrypt_credentials(creds)
    assert "it's a token" not in encrypted
    assert decrypt_credentials(encrypted) == creds


def test_get_connector_credentials_via_secret():
    secret = Secret(slug="s", name="S", secret_type="jira", credentials_encrypted=encrypt_credentials({"api_token": "tok"}))
    connector = Connector(slug="c", name="C", connector_type="jira", secret=secret)
    assert get_connector_credentials(connector) == {"api_token": "tok"}
    assert get_connector_credentials_encrypted(connector) == secret.credentials_encrypted


def test_get_connector_credentials_no_secret_raises():
    connector = Connector(slug="c", name="C", connector_type="jira", secret=None)
    with pytest.raises(ValueError, match="no secret configured"):
        get_connector_credentials(connector)
