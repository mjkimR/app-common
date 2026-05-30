from pydantic import BaseModel


class PaginatedList[T](BaseModel):
    """Generic schema for returning paginated results."""

    items: list[T]
    total_count: int
    offset: int
    limit: int


class DeleteResponse(BaseModel):
    """Schema for resource deletion responses."""

    success: bool
    identity: str | None = None
