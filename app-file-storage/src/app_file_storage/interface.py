from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class FileStorageClient(ABC):
    """Object storage seen as a flat key -> bytes map.

    Every provider must be swappable without changing caller behaviour, so the contract
    below is binding for all of them (`tests/integrate/test_contract.py` enforces it
    against each implementation):

    - Keys are opaque strings, S3-style. `a/b.txt` is a key, not a directory, and a key
      can never address anything outside the configured bucket/root -- `../` must raise.
    - Missing key -> `FileNotFoundError` from `download_file`, `download_file_stream` and
      `get_file_metadata`. `delete_file` on a missing key is a no-op, not an error.
    - `file_exists` returns False only for a genuine not-found. Anything else (denied
      credentials, unreachable backend) raises; it must never be reported as absence.
    - `list_files(prefix)` matches on the **string prefix** of the key, so `list_files("doc")`
      yields both `doc.txt` and `docs/a.txt`.
    - `get_file_metadata` always returns at least `size` (int), `last_modified`
      (timezone-aware `datetime`) and `path` (the key). Providers may add their own keys
      on top -- S3 also returns `content_type` and `etag`.
    """

    @classmethod
    @abstractmethod
    async def from_env(cls) -> "FileStorageClient":
        """Create a file storage client from environment configuration."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the file storage client."""
        pass

    @abstractmethod
    async def download_file(self, file_path: str, version_id: str | None = None) -> bytes:
        """Downloads a file and returns its content as bytes."""
        pass

    @abstractmethod
    def download_file_stream(self, file_path: str) -> AsyncIterator[bytes]:
        """Downloads a file as a stream of bytes."""
        pass

    @abstractmethod
    async def upload_file(self, file_path: str, data: bytes) -> None:
        """Uploads a file with the given data."""
        pass

    @abstractmethod
    async def delete_file(self, file_path: str) -> None:
        """Deletes a file at the given path."""
        pass

    @abstractmethod
    def list_files(self, prefix: str) -> AsyncIterator[str]:
        """Lists files matching a given prefix."""
        pass

    @abstractmethod
    async def file_exists(self, file_path: str) -> bool:
        """Checks if a file exists at the given path."""
        pass

    @abstractmethod
    async def get_file_metadata(self, file_path: str) -> dict[str, Any]:
        """Gets metadata for a file at the given path."""
        pass
