from typing import Any, Generic, Optional, Sequence, TypeVar

from pydantic import BaseModel, computed_field

PageItem = TypeVar("PageItem", bound=Any)


class PaginatedList(BaseModel, Generic[PageItem]):
    """Offset Pagination Items"""

    items: Sequence[PageItem]
    total_count: Optional[int] = None
    offset: int = 0
    limit: Optional[int] = None

    @computed_field
    @property
    def last(self) -> bool | None:
        """Check if the current page is the last page"""
        if self.limit is None or self.total_count is None:
            return None
        return self.offset + self.limit >= self.total_count

    @computed_field
    @property
    def first(self) -> bool:
        return self.offset == 0
