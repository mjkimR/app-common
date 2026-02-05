import pytest
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from app_base.adapter.file_storage.interface import FileStorageClient
from app_base.config import FileStorageSettings


def test_file_storage_client_is_abstract():
    with pytest.raises(
        TypeError,
        match="Can't instantiate abstract class FileStorageClient without an implementation for abstract methods",
    ):
        FileStorageClient()


def test_file_storage_client_abstract_methods():
    expected_abstract_methods = {
        "from_config",
        "close",
        "download_file",
        "download_file_stream",
        "upload_file",
        "delete_file",
        "list_files",
        "file_exists",
        "get_file_metadata",
    }
    assert FileStorageClient.__abstractmethods__ == expected_abstract_methods


class ConcreteFileStorageClient(FileStorageClient):
    async def from_config(cls, settings: FileStorageSettings) -> "FileStorageClient":
        pass

    async def close(self) -> None:
        pass

    async def download_file(self, file_path: str) -> bytes:
        pass

    def download_file_stream(self, file_path: str) -> AsyncIterator[bytes]:
        pass

    async def upload_file(self, file_path: str, data: bytes) -> None:
        pass

    async def delete_file(self, file_path: str) -> None:
        pass

    async def list_files(self, prefix: str) -> list[str]:
        pass

    async def file_exists(self, file_path: str) -> bool:
        pass

    async def get_file_metadata(self, file_path: str) -> dict[str, Any]:
        pass


def test_concrete_file_storage_client_instantiation():
    # Should not raise TypeError when all abstract methods are implemented
    class CompleteFileStorageClient(FileStorageClient):
        async def from_config(cls, settings: FileStorageSettings) -> "FileStorageClient":
            return cls()

        async def close(self) -> None:
            pass

        async def download_file(self, file_path: str) -> bytes:
            return b""

        def download_file_stream(self, file_path: str) -> AsyncIterator[bytes]:
            async def gen():
                yield b""

            return gen()

        async def upload_file(self, file_path: str, data: bytes) -> None:
            pass

        async def delete_file(self, file_path: str) -> None:
            pass

        async def list_files(self, prefix: str) -> list[str]:
            return []

        async def file_exists(self, file_path: str) -> bool:
            return False

        async def get_file_metadata(self, file_path: str) -> dict[str, Any]:
            return {}

    try:
        CompleteFileStorageClient()
    except TypeError:
        pytest.fail("TypeError raised for a complete implementation of FileStorageClient")
