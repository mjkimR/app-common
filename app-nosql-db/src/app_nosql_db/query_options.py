from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True, kw_only=True)
class NoSQLListQueryOptions:
    offset: int = 0
    limit: int = 100
    filters: Sequence[tuple[str, str, Any]] = ()
