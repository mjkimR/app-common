from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field


class SearchItem(BaseModel):
    """Application-owned content. Identity is (source_id, item_id) within a scope."""

    model_config = ConfigDict(extra="forbid")
    source_id: str = Field(min_length=1)
    item_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    title: str = ""
    filters: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchHit(BaseModel):
    source_id: str
    item_id: str
    score: float


class SearchResultItem(SearchItem):
    score: float


class SearchResult(BaseModel):
    items: list[SearchResultItem] = Field(default_factory=list)
    index_ready: bool = False
    candidate_limit_reached: bool = False

    @computed_field
    @property
    def total(self) -> int:
        """Returned count, never a count of all matching points."""
        return len(self.items)


class SyncResult(BaseModel):
    scanned: int = 0
    embedded: int = 0
    refreshed: int = 0
    skipped: int = 0
    deleted: int = 0


class IndexStatus(BaseModel):
    collection_name: str
    profile_id: str
    collection_exists: bool
    index_ready: bool
    last_synced_at: datetime | None = None
    last_result: SyncResult | None = None
