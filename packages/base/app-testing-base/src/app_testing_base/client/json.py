"""AsyncClient subclass with automatic orjson serialization for test payloads."""

from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID

import orjson
from httpx import AsyncClient
from pydantic import BaseModel


def default_json_serializer(obj: Any) -> Any:
    """Serialize objects not natively supported by orjson."""
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (datetime, date, time)):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type '{obj.__class__.__name__}' is not JSON serializable")


class AsyncClientWithJson(AsyncClient):
    """AsyncClient with custom JSON serialization for Enums, Dates, UUIDs, and Pydantic models."""

    async def request(self, *args: Any, **kwargs: Any) -> Any:
        if "json" in kwargs:
            payload = kwargs.pop("json")
            kwargs["content"] = orjson.dumps(payload, default=default_json_serializer)
            headers = kwargs.get("headers")
            if headers is None:
                headers = {}
                kwargs["headers"] = headers
            headers["Content-Type"] = "application/json"
        return await super().request(*args, **kwargs)
