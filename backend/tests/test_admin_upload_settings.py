"""Tests for admin upload settings API."""

import pytest

from app.models import UploadSettings

pytestmark = pytest.mark.asyncio


async def test_get_upload_settings_admin_only(client, auth_headers):
    res = await client.get("/api/admin/upload-settings", headers=auth_headers)
    assert res.status_code == 403


async def test_get_upload_settings_creates_default(client, admin_headers):
    res = await client.get("/api/admin/upload-settings", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert "enabled" in data
    assert "s3_bucket" in data


async def test_update_upload_settings(client, admin_headers):
    res = await client.put(
        "/api/admin/upload-settings",
        headers=admin_headers,
        json={"enabled": True, "s3_bucket": "test-bucket"},
    )
    assert res.status_code == 200
    assert res.json()["enabled"] is True
    assert res.json()["s3_bucket"] == "test-bucket"


async def test_update_partial(client, admin_headers):
    initial = await client.put(
        "/api/admin/upload-settings",
        headers=admin_headers,
        json={"s3_bucket": "first-bucket"},
    )
    res = await client.put(
        "/api/admin/upload-settings",
        headers=admin_headers,
        json={"retention_days": 60},
    )
    assert res.status_code == 200
    assert res.json()["retention_days"] == 60
    assert res.json()["s3_bucket"] == "first-bucket"
