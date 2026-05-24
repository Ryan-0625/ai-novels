"""
Tests: JWT creation, verification, expiry, malformed tokens
"""

import time
import pytest
from datetime import datetime, timezone

from ai_novels.api.auth.jwt import (
    configure_jwt,
    create_access_token,
    verify_jwt,
    JWTException,
)


@pytest.fixture(autouse=True)
def setup_jwt():
    configure_jwt(
        secret="test-secret-key-at-least-16-chars",
        algorithm="HS256",
        expire_minutes=60,
    )


@pytest.mark.asyncio
async def test_create_and_verify():
    token = await create_access_token({
        "sub": "u_001",
        "tenant_id": "t_001",
        "name": "Alice",
    })
    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 20

    payload = await verify_jwt(token)
    assert payload is not None
    assert payload["sub"] == "u_001"
    assert payload["tenant_id"] == "t_001"
    assert payload["name"] == "Alice"


@pytest.mark.asyncio
async def test_expired_token():
    configure_jwt(secret="test-secret-key-at-least-16-chars", expire_minutes=0)
    token = await create_access_token({"sub": "u_001", "tenant_id": "t_001"})
    # 0-minute expiry means token is already expired
    time.sleep(0.1)
    payload = await verify_jwt(token)
    assert payload is None


@pytest.mark.asyncio
async def test_malformed_token():
    payload = await verify_jwt("invalid.jwt.token")
    assert payload is None


@pytest.mark.asyncio
async def test_wrong_secret():
    token = await create_access_token({"sub": "u_001", "tenant_id": "t_001"})
    configure_jwt(secret="different-secret-key-32-chars-long!!")
    payload = await verify_jwt(token)
    assert payload is None  # signature mismatch


@pytest.mark.asyncio
async def test_missing_required_fields():
    token = await create_access_token({"name": "Alice"})  # no sub, no tenant_id
    payload = await verify_jwt(token)
    assert payload is not None  # defaults applied


@pytest.mark.asyncio
async def test_unsupported_algorithm():
    with pytest.raises(ValueError, match="Unsupported algorithm"):
        configure_jwt(secret="test-secret-key-at-least-16-chars", algorithm="none")


@pytest.mark.asyncio
async def test_short_secret():
    with pytest.raises(ValueError, match="at least 16 characters"):
        configure_jwt(secret="short", algorithm="HS256")
