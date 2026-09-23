import asyncio
import time
from typing import Annotated
from urllib.parse import urlencode

import jwt
from app_http_client import get_http_client
from fastapi import Depends
from pydantic import BaseModel, EmailStr

from .config import GoogleAuthSettings, get_google_auth_settings


class GoogleIdentity(BaseModel):
    subject: str
    email: EmailStr
    name: str


class GoogleProvider:
    def __init__(self, settings: Annotated[GoogleAuthSettings, Depends(get_google_auth_settings)]):
        self.settings = settings

    def authorization_url(self, state: str, nonce: str, challenge: str) -> str:
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
            {
                "client_id": self.settings.client_id,
                "redirect_uri": self.settings.redirect_uri,
                "response_type": "code",
                "response_mode": self.settings.response_mode,
                "scope": "openid email profile",
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )

    async def exchange(self, code: str, verifier: str, nonce: str) -> GoogleIdentity:
        client = get_http_client()
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": self.settings.client_id,
                "client_secret": self.settings.client_secret.get_secret_value(),
                "redirect_uri": self.settings.redirect_uri,
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": verifier,
            },
            timeout=15,
        )
        response.raise_for_status()
        token = response.json()["id_token"]
        keys = await _google_keys()
        header = jwt.get_unverified_header(token)
        key = next((key for key in keys if key.get("kid") == header.get("kid")), None)
        if key is None:
            keys = await _google_keys(refresh=True)
            key = next((key for key in keys if key.get("kid") == header.get("kid")), None)
        if key is None:
            raise ValueError("Unknown Google signing key")
        claims = jwt.decode(
            token,
            jwt.PyJWK.from_dict(key).key,
            algorithms=["RS256"],
            audience=self.settings.client_id,
            issuer=["https://accounts.google.com", "accounts.google.com"],
            options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce", "email"]},
        )
        if claims.get("azp", self.settings.client_id) != self.settings.client_id:
            raise ValueError("Unexpected Google authorized party")
        if claims["nonce"] != nonce or claims.get("email_verified") is not True:
            raise ValueError("Google identity verification failed")
        if not isinstance(claims["sub"], str) or not claims["sub"] or len(claims["sub"]) > 255:
            raise ValueError("Invalid Google subject")
        return GoogleIdentity(
            subject=claims["sub"], email=claims["email"], name=str(claims.get("name") or claims["email"])[:255]
        )


_keys: list[dict] = []
_keys_until = 0.0
_keys_lock = asyncio.Lock()


async def _google_keys(*, refresh: bool = False) -> list[dict]:
    global _keys, _keys_until
    async with _keys_lock:
        if _keys and time.monotonic() < _keys_until and not refresh:
            return _keys
        response = await get_http_client().get("https://www.googleapis.com/oauth2/v3/certs", timeout=10)
        response.raise_for_status()
        _keys = response.json()["keys"]
        _keys_until = time.monotonic() + 300
        return _keys
