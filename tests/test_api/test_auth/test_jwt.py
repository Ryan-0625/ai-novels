"""
Tests: JWT creation, verification, expiry, malformed tokens — UT-01 ~ UT-15
"""

import time
import json
import pytest
from datetime import datetime, timezone
from base64 import b64decode

from ai_novels.api.auth.jwt import (
    configure_jwt,
    create_access_token,
    verify_jwt,
    JWTException,
    JWTExpired,
    JWTMalformed,
)


_SECRET = "test-secret-key-at-least-16-chars"


@pytest.fixture(autouse=True)
def setup_jwt():
    configure_jwt(secret=_SECRET, algorithm="HS256", expire_minutes=60)


def _decode_payload(token: str) -> dict:
    """辅助函数: 解码 JWT payload (不验证签名)"""
    import jwt as pyjwt
    return pyjwt.decode(token, options={"verify_signature": False})


# ── UT-01 ~ UT-03: configure_jwt ──

class TestConfigureJWT:
    def test_normal_config(self):
        configure_jwt(secret=_SECRET, algorithm="HS256")
        # 正常配置无异常

    def test_unsupported_algorithm(self):
        with pytest.raises(ValueError, match="Unsupported algorithm"):
            configure_jwt(secret=_SECRET, algorithm="none")

    def test_short_secret(self):
        with pytest.raises(ValueError, match="at least 16 characters"):
            configure_jwt(secret="short", algorithm="HS256")

    def test_empty_secret(self):
        with pytest.raises(ValueError, match="at least 16 characters"):
            configure_jwt(secret="", algorithm="HS256")


# ── UT-04 ~ UT-08: create_access_token ──

class TestCreateAccessToken:
    @pytest.mark.asyncio
    async def test_normal_token(self):
        token = await create_access_token({
            "sub": "u_001",
            "tenant_id": "t_001",
            "name": "Alice",
        })
        assert isinstance(token, str)
        assert len(token.split(".")) == 3  # header.payload.signature
        assert len(token) > 20

        payload = _decode_payload(token)
        assert payload["sub"] == "u_001"
        assert payload["tenant_id"] == "t_001"
        assert payload["name"] == "Alice"
        assert "iat" in payload
        assert "exp" in payload

    @pytest.mark.asyncio
    async def test_unconfigured(self):
        from ai_novels.api.auth import jwt as jwt_module
        jwt_module._JWT_SECRET = ""
        with pytest.raises(JWTException, match="not configured"):
            await create_access_token({"sub": "u_001", "tenant_id": "t_001"})

    @pytest.mark.asyncio
    async def test_missing_sub_defaults(self):
        configure_jwt(secret=_SECRET)
        token = await create_access_token({"tenant_id": "t_001"})
        payload = _decode_payload(token)
        assert payload["sub"] == "anonymous"

    @pytest.mark.asyncio
    async def test_missing_tenant_id_defaults(self):
        configure_jwt(secret=_SECRET)
        token = await create_access_token({"sub": "u_001"})
        payload = _decode_payload(token)
        assert payload["tenant_id"] == "default"

    @pytest.mark.asyncio
    async def test_custom_expiry(self):
        configure_jwt(secret=_SECRET)
        token = await create_access_token(
            {"sub": "u_001", "tenant_id": "t_001"},
            expires_delta=5,
        )
        payload = _decode_payload(token)
        exp = payload["exp"]
        iat = payload["iat"]
        assert exp - iat == 300  # 5 minutes = 300 seconds

    @pytest.mark.asyncio
    async def test_default_expiry(self):
        configure_jwt(secret=_SECRET, expire_minutes=1440)
        token = await create_access_token({"sub": "u_001", "tenant_id": "t_001"})
        payload = _decode_payload(token)
        assert payload["exp"] - payload["iat"] == 86400  # 1440 min = 86400 sec

    @pytest.mark.asyncio
    async def test_all_algorithms(self):
        for alg in ["HS256", "HS384", "HS512"]:
            configure_jwt(secret=_SECRET, algorithm=alg)
            token = await create_access_token({"sub": "u_001", "tenant_id": "t_001"})
            assert token is not None

    @pytest.mark.asyncio
    async def test_iat_is_utc_now(self):
        configure_jwt(secret=_SECRET)
        before = int(datetime.now(timezone.utc).timestamp())
        token = await create_access_token({"sub": "u_001", "tenant_id": "t_001"})
        after = int(datetime.now(timezone.utc).timestamp())
        payload = _decode_payload(token)
        assert before <= payload["iat"] <= after + 1


# ── UT-09 ~ UT-15: verify_jwt ──

class TestVerifyJWT:
    @pytest.mark.asyncio
    async def test_valid_token(self):
        configure_jwt(secret=_SECRET)
        token = await create_access_token({"sub": "u_001", "tenant_id": "t_001"})
        payload = await verify_jwt(token)
        assert payload is not None
        assert payload["sub"] == "u_001"
        assert payload["tenant_id"] == "t_001"

    @pytest.mark.asyncio
    async def test_expired_token(self):
        configure_jwt(secret=_SECRET, expire_minutes=0)
        token = await create_access_token({"sub": "u_001", "tenant_id": "t_001"})
        time.sleep(0.1)
        payload = await verify_jwt(token)
        assert payload is None

    @pytest.mark.asyncio
    async def test_wrong_signature(self):
        configure_jwt(secret=_SECRET)
        token = await create_access_token({"sub": "u_001", "tenant_id": "t_001"})
        configure_jwt(secret="different-secret-32-chars-long!!")
        payload = await verify_jwt(token)
        assert payload is None

    @pytest.mark.asyncio
    async def test_malformed_string(self):
        payload = await verify_jwt("this.is.not.a.valid.jwt")
        assert payload is None

    @pytest.mark.asyncio
    async def test_empty_string(self):
        payload = await verify_jwt("")
        assert payload is None

    @pytest.mark.asyncio
    async def test_none_token(self):
        payload = await verify_jwt(None)  # type: ignore
        assert payload is None

    @pytest.mark.asyncio
    async def test_unconfigured_secret(self):
        from ai_novels.api.auth import jwt as jwt_module
        jwt_module._JWT_SECRET = ""
        payload = await verify_jwt("some.token.here")
        assert payload is None

    @pytest.mark.asyncio
    async def test_missing_required_field(self):
        configure_jwt(secret=_SECRET)
        token = await create_access_token({"name": "Alice"})  # no sub, no tenant_id
        payload = await verify_jwt(token)
        assert payload is not None  # defaults applied at creation
        assert payload["sub"] == "anonymous"
        assert payload["tenant_id"] == "default"

    @pytest.mark.asyncio
    async def test_token_with_extra_claims(self):
        token = await create_access_token({
            "sub": "u_001",
            "tenant_id": "t_001",
            "custom_claim": "custom_value",
            "roles": ["admin", "editor"],
        })
        payload = await verify_jwt(token)
        assert payload["custom_claim"] == "custom_value"
        assert "admin" in payload["roles"]

    @pytest.mark.asyncio
    async def test_tampered_token(self):
        configure_jwt(secret=_SECRET)
        token = await create_access_token({"sub": "u_001", "tenant_id": "t_001"})
        parts = token.split(".")
        parts[1] = "eyJzdWIiOiJoYWNrZWQifQ"  # tampered payload
        tampered = ".".join(parts)
        payload = await verify_jwt(tampered)
        assert payload is None
