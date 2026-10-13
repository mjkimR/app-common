"""Real backends for the file-storage contract tests.

The unit tests mock aiobotocore wholesale, which can only confirm that the code calls
boto the way the test author *believed* boto works. These run against a real
S3 (SeaweedFS in a container) and a real filesystem instead.

The S3 half needs Docker and costs ~6s to spin up, so it is marked `docker` and
deselected by default -- `just test` stays fast and infra-free. `just test-docker`
runs it, and so does CI on every push. The local-filesystem half always runs.
"""

import itertools
import os
from collections.abc import AsyncIterator, Iterator

import aiobotocore.session
import pytest
import pytest_asyncio
from app_file_storage.providers.local import LocalStorageProvider
from app_file_storage.providers.s3 import S3StorageProvider

SEAWEEDFS_IMAGE = os.environ.get("APP_TEST_SEAWEEDFS_IMAGE", "chrislusf/seaweedfs:4.48")
S3_ACCESS_KEY = "app-common-test"
S3_SECRET_KEY = "app-common-test-secret"

_bucket_counter = itertools.count()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark everything that needs the SeaweedFS container as `docker`.

    `provider` resolves its backend with `getfixturevalue`, so at collection time pytest
    cannot see that the `s3_provider` parameter pulls in `s3_endpoint` -- hence the
    callspec check, not just `fixturenames`.
    """
    container_fixtures = {"s3_endpoint", "bucket", "s3_provider"}

    for item in items:
        needs_container = bool(container_fixtures & set(getattr(item, "fixturenames", ())))
        params = getattr(getattr(item, "callspec", None), "params", {})
        needs_container |= params.get("provider") == "s3_provider"

        if needs_container:
            item.add_marker(pytest.mark.docker)


@pytest.fixture(scope="session")
def s3_endpoint() -> Iterator[str]:
    """Start authenticated SeaweedFS once for the session and yield its S3 endpoint."""
    docker = pytest.importorskip("docker", reason="Docker SDK is required for the S3 integration tests")
    from testcontainers.core.container import DockerContainer
    from testcontainers.core.wait_strategies import HttpWaitStrategy

    try:
        docker.from_env().ping()
    except Exception as e:  # daemon not running, socket missing, ...
        pytest.skip(f"Docker is not available: {e}")

    container = (
        DockerContainer(SEAWEEDFS_IMAGE)
        .with_command("mini -dir=/data -ip=127.0.0.1 -ip.bind=0.0.0.0")
        .with_exposed_ports(8333)
        .with_env("AWS_ACCESS_KEY_ID", S3_ACCESS_KEY)
        .with_env("AWS_SECRET_ACCESS_KEY", S3_SECRET_KEY)
        .waiting_for(HttpWaitStrategy(8333, "/").for_status_code(403).with_startup_timeout(90))
    )
    with container as seaweedfs:
        yield f"http://{seaweedfs.get_container_host_ip()}:{seaweedfs.get_exposed_port(8333)}"


def s3_client(endpoint: str, *, access_key: str = S3_ACCESS_KEY, secret_key: str = S3_SECRET_KEY):
    """An aiobotocore S3 client context manager pointed at the test SeaweedFS."""
    return aiobotocore.session.get_session().create_client(
        "s3",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="us-east-1",
        endpoint_url=endpoint,
    )


@pytest_asyncio.fixture
async def bucket(s3_endpoint: str) -> AsyncIterator[str]:
    """A fresh, empty bucket per test.

    A new bucket rather than emptying a shared one: it isolates tests without a teardown
    pass, and the container is thrown away at the end of the session anyway.
    """
    name = f"contract-{next(_bucket_counter):03d}"
    async with s3_client(s3_endpoint) as client:
        await client.create_bucket(Bucket=name)
    yield name


@pytest_asyncio.fixture
async def s3_provider(s3_endpoint: str, bucket: str) -> AsyncIterator[S3StorageProvider]:
    async with s3_client(s3_endpoint) as client:
        yield S3StorageProvider(context=None, client=client, bucket_name=bucket)


@pytest.fixture
def local_provider(tmp_path) -> LocalStorageProvider:
    return LocalStorageProvider(tmp_path / "storage")


@pytest.fixture(params=["local_provider", "s3_provider"])
def provider(request):
    """Every FileStorageClient implementation, so the contract is checked against each.

    Sync on purpose: resolving an async fixture via `getfixturevalue` from inside an
    async fixture would re-enter the running event loop and blow up.
    """
    return request.getfixturevalue(request.param)
