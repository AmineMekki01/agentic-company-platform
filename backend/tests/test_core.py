"""Tests for core utility modules: security, encryption, pricing, config, logging."""

import jwt
import pytest
from cryptography.fernet import Fernet

from app.core.config import Settings, settings
from app.core.encryption import EncryptionService
from app.core.logging import configure_logging, get_logger
from app.core.pricing import estimate_cost
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


# ─── security.py ───


def test_hash_and_verify_password():
    hashed = hash_password("mysecret")
    assert verify_password("mysecret", hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("mysecret")
    assert verify_password("wrong", hashed) is False


def test_create_and_decode_token():
    import uuid

    uid = uuid.uuid4()
    token = create_access_token(uid, "user")
    payload = decode_access_token(token)
    assert payload["sub"] == str(uid)
    assert payload["role"] == "user"


def test_decode_expired_token():
    import uuid
    from datetime import UTC, datetime, timedelta

    uid = uuid.uuid4()
    payload = {
        "sub": str(uid),
        "role": "user",
        "exp": datetime.now(UTC) - timedelta(hours=1),
        "iat": datetime.now(UTC),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)


def test_decode_invalid_token():
    with pytest.raises(jwt.PyJWTError):
        decode_access_token("garbage.token.here")


# ─── encryption.py ───


def test_encrypt_decrypt_roundtrip(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "fernet_key", key)
    svc = EncryptionService()
    encrypted = svc.encrypt("my secret data")
    assert encrypted != "my secret data"
    assert svc.decrypt(encrypted) == "my secret data"


def test_decrypt_wrong_key(monkeypatch):
    key1 = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "fernet_key", key1)
    svc1 = EncryptionService()
    encrypted = svc1.encrypt("data")

    key2 = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "fernet_key", key2)
    svc2 = EncryptionService()
    with pytest.raises(Exception):
        svc2.decrypt(encrypted)


def test_encrypt_empty_string(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "fernet_key", key)
    svc = EncryptionService()
    encrypted = svc.encrypt("")
    assert svc.decrypt(encrypted) == ""


def test_no_fernet_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", "")
    with pytest.raises(RuntimeError, match="FERNET_KEY is required"):
        EncryptionService()


# ─── pricing.py ───


def test_estimate_cost_known_model():
    cost = estimate_cost("gpt-5.4", input_tokens=1000, output_tokens=1000)
    assert cost == round(1000 / 1000 * 0.0025 + 1000 / 1000 * 0.015, 6)


def test_estimate_cost_prefix_match():
    cost = estimate_cost("gpt-5.4-something-custom", input_tokens=100, output_tokens=50)
    expected = round(100 / 1000 * 0.0025 + 50 / 1000 * 0.015, 6)
    assert cost == expected


def test_estimate_cost_unknown_model_raises():
    with pytest.raises(ValueError, match="Unknown model"):
        estimate_cost("nonexistent-model", 100, 100)


def test_estimate_cost_zero_tokens():
    cost = estimate_cost("gpt-5.4", 0, 0)
    assert cost == 0.0


def test_estimate_cost_calculation():
    cost = estimate_cost("gpt-5.4-nano", input_tokens=500, output_tokens=200)
    expected = round(500 / 1000 * 0.0002 + 200 / 1000 * 0.0015, 6)
    assert cost == expected


# ─── config.py ───


def test_settings_has_required_fields():
    assert settings.app_name
    assert settings.jwt_secret
    assert settings.database_url
    assert settings.qdrant_url
    assert settings.redis_url


def test_settings_defaults():
    s = Settings()
    assert s.environment == "development"
    assert s.app_name == "Agentic Company Platform"
    assert "http://localhost:5173" in s.cors_origins


# ─── logging.py ───


def test_configure_logging():
    configure_logging()


def test_get_logger():
    logger = get_logger("test_module")
    assert logger.name == "test_module"
