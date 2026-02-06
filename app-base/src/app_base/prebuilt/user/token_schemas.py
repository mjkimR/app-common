import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"]


class TokenPayload(BaseModel):
    # Backward/compat field name used in this project
    user_id: Optional[uuid.UUID] = None

    # Standard JWT-ish fields (kept optional to allow gradual rollout)
    sub: Optional[str] = None
    iss: Optional[str] = None
    aud: Optional[str] = None
    exp: Optional[int] = None
    iat: Optional[int] = None
    nbf: Optional[int] = None
    jti: Optional[str] = None
    typ: Optional[str] = Field(default=None, description="Token type, e.g. 'access' or 'refresh'")

    @model_validator(mode="before")
    @classmethod
    def _fill_user_id_from_sub(cls, data):
        # If issuer starts sending only `sub`, keep `user_id` working.
        if isinstance(data, dict) and data.get("user_id") is None and data.get("sub"):
            data = {**data, "user_id": data.get("sub")}
        return data
