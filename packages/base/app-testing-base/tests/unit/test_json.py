"""Unit tests for AsyncClientWithJson serialization."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

import pytest
from app_testing_base.client import AsyncClientWithJson
from fastapi import FastAPI, Request
from httpx import ASGITransport
from pydantic import BaseModel


class StatusEnum(StrEnum):
    ACTIVE = "active"
    PENDING = "pending"


class PayloadModel(BaseModel):
    title: str
    count: int


app = FastAPI()


@app.post("/test-serialize")
async def echo_payload(request: Request):
    body = await request.json()
    return body


@pytest.mark.asyncio
async def test_async_client_json_serializer():
    uid = uuid.uuid4()
    now = datetime.now(UTC)

    payload = {
        "status": StatusEnum.ACTIVE,
        "uuid": uid,
        "created_at": now,
        "nested": PayloadModel(title="nested", count=42),
    }

    async with AsyncClientWithJson(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        res = await client.post("/test-serialize", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "active"
        assert data["uuid"] == str(uid)
        assert data["created_at"] == now.isoformat()
        assert data["nested"] == {"title": "nested", "count": 42}
