from typing import Literal

from pydantic import BaseModel

from app_prebuilt_auth.user.token_schemas import Token


class GoogleLoginResult(BaseModel):
    status: Literal["approved", "pending", "rejected", "suspended"]
    email: str
    tokens: Token | None = None


class GoogleLoginOptions(BaseModel):
    enabled: bool
