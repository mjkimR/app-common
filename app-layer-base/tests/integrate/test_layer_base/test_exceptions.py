import pytest
from app_layer_base.base.exceptions.basic import BadRequestException
from app_layer_base.base.exceptions.handler import set_exception_handler
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, OperationalError

app = FastAPI()
set_exception_handler(app)
router = APIRouter()


@router.get("/integrity-error")
async def trigger_integrity_error():
    # Simulate an IntegrityError from SQLAlchemy
    # We raise it wrapped in a way similar to what SQLAlchemy does
    raise IntegrityError(
        "Simulated Integrity Error", params={}, orig=Exception("duplicate key value violates unique constraint")
    )


@router.get("/operational-error")
async def trigger_operational_error():
    # Simulate an OperationalError
    raise OperationalError("Simulated Operational Error", params={}, orig=Exception("connection refused"))


@router.get("/custom-exception")
async def trigger_custom_exception():
    raise BadRequestException(message="This is a custom bad request", log_message="Custom log message")


@router.get("/general-exception")
async def trigger_general_exception():
    raise Exception("This is a general unhandled exception")


@router.get("/value-error")
async def trigger_value_error():
    raise ValueError("This is a programming error, not client input")


app.include_router(router)


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


async def test_integrity_error_handler(client):
    response = client.get("/integrity-error")
    assert response.status_code == 409
    data = response.json()
    assert data["title"] == "Data integrity violation"
    assert "Data integrity violation" in data["detail"]


async def test_operational_error_handler(client):
    response = client.get("/operational-error")
    assert response.status_code == 500
    data = response.json()
    assert data["title"] == "Database error"


async def test_custom_exception_handler(client):
    response = client.get("/custom-exception")
    assert response.status_code == 400
    data = response.json()
    assert data["title"] == "Bad Request"
    assert data["detail"] == "This is a custom bad request"


async def test_general_exception_handler(client):
    response = client.get("/general-exception")
    assert response.status_code == 500
    data = response.json()
    assert data["title"] == "Internal Server Error"
    assert data["detail"] == "An unexpected internal server error occurred."


async def test_value_error_is_a_server_error(client):
    """No blanket ValueError->400: a stray ValueError is a bug and must be a 500."""
    response = client.get("/value-error")
    assert response.status_code == 500
    data = response.json()
    assert data["title"] == "Internal Server Error"
