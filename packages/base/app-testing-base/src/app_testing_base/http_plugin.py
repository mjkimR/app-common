"""HTTP-only pytest fixtures; no database setup or dependency overrides.

Load ``app_testing_base.http_plugin`` in the root conftest and provide an ``app``
fixture. The existing DB-aware ``app_testing_base.plugin`` remains independent.
"""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app() -> FastAPI:
    """Override with the consumer's application factory, including its configuration."""
    raise NotImplementedError("Define an app fixture returning your FastAPI application to use http_client.")


@pytest.fixture
def client_headers() -> dict[str, str]:
    """Default request headers; override for application authentication."""
    return {}


@pytest.fixture
def http_client(app: FastAPI, client_headers: dict[str, str]) -> Iterator[TestClient]:
    """Serve the app with its real lifespan and resource ownership, without sockets."""
    with TestClient(app, headers=client_headers) as client:
        yield client
