import uuid

from pydantic import BaseModel, Field


class DeleteResponse(BaseModel):
    success: bool = True
    message: str | None = None

    identity: str | uuid.UUID | None = Field(default=None, description="The identity of the deleted object.")
    representation: str | None = Field(default=None, description="The string representation of the deleted object.")

    meta: dict = Field(
        default_factory=dict,
        description="Additional metadata about the delete operation.",
    )


class MultipleDeleteResponse(BaseModel):
    deleted_count: int = 0
    failed_count: int = 0
    messages: list[str] = Field(default_factory=list, description="Messages related to the delete operations.")

    meta: dict = Field(
        default_factory=dict,
        description="Additional metadata about the delete operation.",
    )
