from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, computed_field


class PaginatedList[PageItem: Any](BaseModel):
    """Offset Pagination Items"""

    items: Sequence[PageItem]
    total_count: int | None = None
    offset: int = 0
    limit: int | None = None

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
