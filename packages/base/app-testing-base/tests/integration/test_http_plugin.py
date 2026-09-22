"""Exercise the standalone plugin in an isolated consumer pytest process."""

pytest_plugins = ["pytester"]


def test_http_only_plugin_lifespan_headers_and_exception_cleanup(pytester):
    pytester.makeconftest("""
from contextlib import asynccontextmanager
import pytest
from fastapi import FastAPI, Request

pytest_plugins = ["app_testing_base.http_plugin"]
events = []

@pytest.fixture
def session():
    raise AssertionError("HTTP-only tests must not request a DB session")

@pytest.fixture
def app():
    @asynccontextmanager
    async def lifespan(app):
        events.append("start")
        try:
            yield
        finally:
            events.append("stop")
    app = FastAPI(lifespan=lifespan)
    @app.get("/")
    def read(request: Request):
        return {"key": request.headers.get("x-api-key"), "started": events[-1]}
    @app.get("/fail")
    def fail():
        raise RuntimeError("request failed")
    app.dependency_overrides[read] = fail
    return app

@pytest.fixture
def client_headers():
    return {"X-API-Key": "test-key"}

@pytest.fixture(autouse=True)
def verify_cleanup(app):
    overrides = app.dependency_overrides.copy()
    yield
    assert events == ["start", "stop"]
    assert app.dependency_overrides == overrides
    events.clear()
""")
    pytester.makepyfile("""
import pytest

def test_request(http_client):
    assert http_client.get("/").json() == {"key": "test-key", "started": "start"}

def test_request_exception(http_client):
    with pytest.raises(RuntimeError, match="request failed"):
        http_client.get("/fail")
""")
    result = pytester.runpytest_subprocess("-q")
    result.assert_outcomes(passed=2)


def test_missing_app_explains_configuration(pytester):
    pytester.makeconftest('pytest_plugins = ["app_testing_base.http_plugin"]')
    pytester.makepyfile("def test_request(http_client): pass")
    result = pytester.runpytest_subprocess("-q")
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*Define an app fixture returning your FastAPI application*"])
