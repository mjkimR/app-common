"""HTTP Client fixtures for FastAPI API testing."""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app_testing_base.client.json import AsyncClientWithJson


@pytest.fixture
def app() -> FastAPI:
    """FastAPI application instance for tests.

    Override this fixture in your top-level `tests/conftest.py` if writing E2E tests:

        @pytest.fixture
        def app():
            from app.main import create_app
            return create_app()
    """
    raise NotImplementedError(
        "No 'app' fixture defined. To use the 'client' fixture, define an 'app' fixture "
        "in your conftest.py that returns your FastAPI application instance."
    )


@pytest.fixture
def client_headers() -> dict[str, str]:
    """Default headers for test client. Override in conftest.py to provide default auth/headers."""
    return {}


@pytest_asyncio.fixture(name="client")
async def client(
    app: FastAPI,
    session: AsyncSession,
    client_headers: dict[str, str],
) -> AsyncIterator[AsyncClientWithJson]:
    """AsyncClient fixture configured with ASGITransport and session dependency override."""
    from app_layer_base.core.database.deps import get_session

    app.dependency_overrides[get_session] = lambda: session

    async with AsyncClientWithJson(
        transport=ASGITransport(app=app),  # type: ignore[arg-type]
        base_url="http://testserver/",
        headers=client_headers,
        follow_redirects=True,
    ) as test_client:
        yield test_client

    app.dependency_overrides.pop(get_session, None)


client_fixture = client
