import json
import time

import httpx
import jwt
import pytest
from app_prebuilt_auth.google import provider as provider_module
from app_prebuilt_auth.google.config import GoogleAuthSettings
from app_prebuilt_auth.google.provider import GoogleProvider
from cryptography.hazmat.primitives.asymmetric import rsa


@pytest.fixture
def google_settings():
    return GoogleAuthSettings(
        enabled=True,
        client_id="client",
        client_secret="secret",
        cookie_secure=False,
        redirect_uri="http://localhost/api/v1/auth/google/callback",
        frontend_url="http://localhost/",
    )


@pytest.mark.parametrize(
    "claim,value",
    [
        ("aud", "wrong-client"),
        ("azp", "wrong-client"),
        ("iss", "https://evil.example"),
        ("nonce", "wrong-nonce"),
        ("exp", 1),
        ("email_verified", False),
        ("sub", ""),
    ],
)
async def test_provider_rejects_untrusted_claims(google_settings, monkeypatch, claim, value):
    await exercise(google_settings, monkeypatch, {claim: value}, False)


async def test_provider_accepts_signed_google_identity(google_settings, monkeypatch):
    await exercise(google_settings, monkeypatch, {}, True)


async def exercise(settings, monkeypatch, overrides, accepted):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    key["kid"] = "test-key"
    claims = {
        "iss": "https://accounts.google.com",
        "aud": "client",
        "sub": "stable-id",
        "nonce": "nonce",
        "iat": int(time.time()),
        "exp": int(time.time()) + 60,
        "email": "test@example.com",
        "email_verified": True,
    }
    claims.update(overrides)
    token = jwt.encode(claims, private, algorithm="RS256", headers={"kid": "test-key"})

    def respond(request):
        if request.url.path == "/token":
            assert b"code_verifier=verifier" in request.content
            return httpx.Response(200, json={"id_token": token})
        return httpx.Response(200, json={"keys": [key]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(provider_module, "get_http_client", lambda: client)
        monkeypatch.setattr(provider_module, "_keys", [])
        monkeypatch.setattr(provider_module, "_keys_until", 0)
        if accepted:
            result = await GoogleProvider(settings).exchange("code", "verifier", "nonce")
            assert result.subject == "stable-id"
        else:
            with pytest.raises((ValueError, jwt.PyJWTError)):
                await GoogleProvider(settings).exchange("code", "verifier", "nonce")


@pytest.mark.parametrize(
    "overrides",
    [
        {"frontend_url": "https://evil.example/"},
        {"cookie_path": "/other"},
        {"redirect_uri": "http://public.example/api/v1/auth/google/callback"},
        {"client_secret": ""},
    ],
)
def test_invalid_configuration_is_rejected(google_settings, overrides):
    with pytest.raises(ValueError):
        GoogleAuthSettings(**(google_settings.model_dump() | overrides))
