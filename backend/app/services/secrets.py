"""Secret credential storage and resolution."""

import ast
import json
from typing import Any

from app.core.encryption import EncryptionService
from app.models.connector import Connector


def encrypt_credentials(credentials: dict[str, Any]) -> str:
    """Serialize and encrypt a credentials dict for storage."""
    crypto = EncryptionService()
    return crypto.encrypt(json.dumps(credentials))


def decrypt_credentials(credentials_encrypted: str) -> dict[str, Any]:
    """Decrypt and parse a stored credentials blob."""
    crypto = EncryptionService()
    decrypted = crypto.decrypt(credentials_encrypted)
    try:
        return json.loads(decrypted)
    except json.JSONDecodeError:
        return ast.literal_eval(decrypted)


def get_connector_credentials_encrypted(connector: Connector) -> str:
    """Resolve the raw (still-encrypted) credentials string for a connector's secret.

    Relies on Connector.secret being eagerly loaded (lazy="selectin" on the
    model), so this is a plain attribute access - no DB session needed here.
    """
    if connector.secret is None:
        raise ValueError(f"Connector '{connector.slug}' has no secret configured")
    return connector.secret.credentials_encrypted


def get_connector_credentials(connector: Connector) -> dict[str, Any]:
    """Resolve, decrypt, and parse a connector's secret credentials."""
    return decrypt_credentials(get_connector_credentials_encrypted(connector))
