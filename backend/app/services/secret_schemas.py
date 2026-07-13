"""Typed field registry for Secret credentials, per secret_type."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SecretField:
    key: str
    label: str
    sensitive: bool
    required: bool = True


SECRET_TYPE_SCHEMAS: dict[str, list[SecretField]] = {
    "jira": [
        SecretField("base_url", "Base URL", sensitive=False),
        SecretField("email", "Account Email", sensitive=False),
        SecretField("api_token", "API Token", sensitive=True),
    ],
    "s3": [
        SecretField("access_key", "Access Key ID", sensitive=True),
        SecretField("secret_key", "Secret Access Key", sensitive=True),
        SecretField("region", "Region", sensitive=False, required=False),
        SecretField("endpoint_url", "Endpoint URL", sensitive=False, required=False),
    ],
    "notion": [
        SecretField("token", "Integration Token", sensitive=True),
    ],
    "gdrive": [
        SecretField("service_account_json", "Service Account JSON", sensitive=True),
        SecretField("delegated_user", "Delegated User", sensitive=False, required=False),
    ],
}


def validate_credentials(secret_type: str, credentials: dict) -> list[str]:
    """Return a list of missing required field names for this secret_type. Empty = valid."""
    schema = SECRET_TYPE_SCHEMAS.get(secret_type)
    if schema is None:
        return []
    return [f.key for f in schema if f.required and not credentials.get(f.key)]


def non_sensitive_fields(secret_type: str, credentials: dict) -> dict:
    """Return only the non-sensitive fields of a decrypted credentials dict, safe to return to clients."""
    schema = SECRET_TYPE_SCHEMAS.get(secret_type)
    if schema is None:
        return {}
    return {f.key: credentials[f.key] for f in schema if not f.sensitive and f.key in credentials}
