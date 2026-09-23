import os
from collections.abc import AsyncIterator, Iterator
from uuid import uuid4

import pytest
import pytest_asyncio
from app_document_store import FirestoreDocumentStore, FirestoreSettings, open_firestore

EMULATOR_IMAGE = "gcr.io/google.com/cloudsdktool/google-cloud-cli:573.0.0-emulators"


@pytest.fixture(scope="session")
def emulator_host() -> Iterator[str]:
    """Opt-in real service tests fail if the required backend cannot start."""
    external = os.environ.get("FIRESTORE_EMULATOR_HOST")
    if external:
        yield external
        return
    from testcontainers.core.container import DockerContainer
    from testcontainers.core.wait_strategies import LogMessageWaitStrategy

    container = (
        DockerContainer(EMULATOR_IMAGE)
        .with_command("gcloud emulators firestore start --host-port=0.0.0.0:8080 --project=demo-document-store --quiet")
        .with_exposed_ports(8080)
        .waiting_for(LogMessageWaitStrategy("Dev App Server is now running").with_startup_timeout(90))
    )
    with container as emulator:
        yield f"{emulator.get_container_host_ip()}:{emulator.get_exposed_port(8080)}"


@pytest_asyncio.fixture
async def stores(emulator_host, monkeypatch) -> AsyncIterator[tuple[FirestoreDocumentStore, FirestoreDocumentStore]]:
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", emulator_host)
    # Never use developer project IDs. Fresh paths isolate tests even on an external emulator.
    settings = FirestoreSettings(project_id="demo-document-store", namespace=uuid4().hex, mode="emulator")
    async with open_firestore(settings) as client:
        yield (
            FirestoreDocumentStore(client, "reports", namespace=settings.namespace, batch_size=2),
            FirestoreDocumentStore(client, "reports", namespace=uuid4().hex),
        )
