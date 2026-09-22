from typing import Literal

from app_prebuilt_user.token_schemas import Token
from pydantic import BaseModel


class GoogleLoginResult(BaseModel):
    status: Literal["approved", "pending", "rejected", "suspended"]
    email: str
    tokens: Token | None = None


class GoogleLoginOptions(BaseModel):
    enabled: bool
