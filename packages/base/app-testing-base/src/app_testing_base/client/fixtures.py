"""HTTP Client fixtures for FastAPI API testing."""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app_testing_base.client.json import AsyncClientWithJson


def _discover_fastapi_app() -> FastAPI | None:
    """Attempt to auto-discover FastAPI app from common module locations."""
    candidates = [
        ("app.main", "app"),
        ("app.main", "create_app"),
        ("main", "app"),
        ("main", "create_app"),
    ]
    for mod_name, attr_name in candidates:
        try:
            mod = __import__(mod_name, fromlist=[attr_name])
            obj = getattr(mod, attr_name, None)
            if obj is not None:
                if isinstance(obj, FastAPI):
                    return obj
                if callable(obj):
                    res = obj()
                    if isinstance(res, FastAPI):
                        return res
        except (ImportError, AttributeError):
            continue
        except Exception:
            continue
    return None


@pytest.fixture
def app() -> FastAPI:
    """FastAPI application instance for tests.

    Auto-discovers from `app.main:app` or `app.main:create_app()` if available.
    Override this fixture in your top-level `tests/conftest.py` if custom setup is needed:

        @pytest.fixture
        def app():
            from app.main import create_app
            return create_app()
    """
    discovered = _discover_fastapi_app()
    if discovered is not None:
        return discovered

    raise NotImplementedError(
        "No FastAPI 'app' could be auto-discovered (checked app.main:app, app.main:create_app). "
        "To use the 'client' fixture, define an 'app' fixture in your conftest.py "
        "that returns your FastAPI application instance."
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
