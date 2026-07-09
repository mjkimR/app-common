from pydantic import BaseModel, Field

from app_layer_base.base.repos.base import PrimaryKeyType


class DeleteResponse(BaseModel):
    success: bool = True
    message: str | None = None

    identity: PrimaryKeyType | None = Field(default=None, description="The identity of the deleted object.")
    representation: str | None = Field(default=None, description="The string representation of the deleted object.")

    meta: dict = Field(
        default_factory=dict,
        description="Additional metadata about the delete operation.",
    )


class MultipleDeleteResponse(BaseModel):
    deleted_count: int = 0
    failed_count: int = Field(
        default=0,
        description="Requested primary keys that were not deleted (not found or already removed): "
        "len(requested) - deleted_count.",
    )

    meta: dict = Field(
        default_factory=dict,
        description="Additional metadata about the delete operation.",
    )
