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


@app.post("/test-body")
async def echo_body(request: Request):
    return {"content_type": request.headers.get("content-type"), "body": (await request.body()).decode()}


@pytest.mark.asyncio
async def test_a_form_or_raw_body_is_sent_as_it_is():
    """Regression: httpx always passes `json` (as None), which used to replace every other body with `null`."""
    async with AsyncClientWithJson(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        form = await client.post("/test-body", data={"username": "a@example.com", "password": "secret"})
        raw = await client.post("/test-body", content=b"plain", headers={"Content-Type": "text/plain"})
        empty = await client.post("/test-body")

    assert form.json() == {
        "content_type": "application/x-www-form-urlencoded",
        "body": "username=a%40example.com&password=secret",
    }
    assert raw.json() == {"content_type": "text/plain", "body": "plain"}
    assert empty.json()["body"] == ""
