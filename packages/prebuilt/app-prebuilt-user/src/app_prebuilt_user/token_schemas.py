import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"]
    # Exchanged at `/login/refresh` for a new pair before it expires; each exchange extends the session.
    refresh_token: str | None = None
    # Seconds until the access token expires, so a client can refresh ahead of time.
    expires_in: int | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPayload(BaseModel):
    # Backward/compat field name used in this project
    user_id: uuid.UUID | None = None

    # Standard JWT-ish fields (kept optional to allow gradual rollout)
    sub: str | None = None
    iss: str | None = None
    aud: str | None = None
    exp: int | None = None
    iat: int | None = None
    nbf: int | None = None
    jti: str | None = None
    typ: str | None = Field(default=None, description="Token type, e.g. 'access' or 'refresh'")
    # Refresh tokens only: ties the token to the password it was issued under.
    pwd: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _fill_user_id_from_sub(cls, data):
        # If issuer starts sending only `sub`, keep `user_id` working.
        if isinstance(data, dict) and data.get("user_id") is None and data.get("sub"):
            data = {**data, "user_id": data.get("sub")}
        return data
