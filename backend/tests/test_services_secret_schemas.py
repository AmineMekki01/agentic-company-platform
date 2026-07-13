"""Tests for the typed secret field registry (app.services.secret_schemas)."""

from app.services.secret_schemas import non_sensitive_fields, validate_credentials


def test_validate_credentials_missing_required_field():
    missing = validate_credentials("jira", {"base_url": "https://x.atlassian.net"})
    assert set(missing) == {"email", "api_token"}


def test_validate_credentials_all_present():
    missing = validate_credentials(
        "jira", {"base_url": "https://x.atlassian.net", "email": "a@b.com", "api_token": "tok"}
    )
    assert missing == []


def test_validate_credentials_optional_field_not_required():
    missing = validate_credentials("s3", {"access_key": "a", "secret_key": "b"})
    assert missing == []


def test_validate_credentials_custom_type_has_no_schema():
    assert validate_credentials("custom", {"anything": "goes"}) == []


def test_non_sensitive_fields_filters_out_sensitive_keys():
    creds = {"base_url": "https://x.atlassian.net", "email": "a@b.com", "api_token": "super-secret"}
    revealed = non_sensitive_fields("jira", creds)
    assert revealed == {"base_url": "https://x.atlassian.net", "email": "a@b.com"}
    assert "api_token" not in revealed


def test_non_sensitive_fields_custom_type_reveals_nothing():
    assert non_sensitive_fields("custom", {"anything": "goes"}) == {}
