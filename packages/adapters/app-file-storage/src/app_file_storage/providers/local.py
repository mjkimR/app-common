import asyncio
import datetime
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import aiofiles
import aiofiles.os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app_file_storage.interface import FileStorageClient


class LocalFileStorageSettings(BaseSettings):
    """Settings for when the file storage provider is 'local'."""

    bucket_name: str = Field(
        default="local_storage", description="Root directory name used as the local storage bucket"
    )
    model_config = SettingsConfigDict(env_prefix="FS_LOCAL_")


class LocalStorageProvider(FileStorageClient):
    """Manages file operations on the local filesystem."""

    def __init__(self, root_path: str | Path):
        # Resolved once, here: `_get_full_path` resolves every key, so an unresolved root
        # (a relative path -- which is exactly what `from_env` builds -- or one with a
        # symlinked parent like macOS /tmp) would make `relative_to(self.root_path)` in
        # `list_files` raise ValueError.
        self.root_path = Path(root_path).resolve()
        self.root_path.mkdir(parents=True, exist_ok=True)

    @classmethod
    async def from_env(cls) -> FileStorageClient:
        config = LocalFileStorageSettings()
        root_path = Path(config.bucket_name)
        root_path.mkdir(parents=True, exist_ok=True)
        return cls(root_path)

    async def close(self) -> None:
        """Local storage does not require a client to be closed."""
        pass

    def _get_full_path(self, file_path: str) -> Path:
        """Resolve a key to an absolute path, refusing anything outside the storage root.

        An S3 key cannot escape its bucket, so a `../` in a key must not escape the root
        here either -- otherwise a caller-supplied path reads or overwrites arbitrary
        files on the host.
        """
        full_path = self.root_path.joinpath(file_path).resolve()
        if full_path != self.root_path and self.root_path not in full_path.parents:
            raise ValueError(f"Path escapes the storage root: {file_path!r}")
        return full_path

    async def download_file(self, file_path: str, version_id: str | None = None) -> bytes:
        """Downloads a file and returns its content as bytes."""
        if version_id is not None:
            raise NotImplementedError("Versioning is not supported in local storage.")

        path = self._get_full_path(file_path)
        if not await aiofiles.os.path.exists(path):
            raise FileNotFoundError(f"File not found at {file_path}")

        async with aiofiles.open(path, "rb") as f:
            return await f.read()

    async def download_file_stream(self, file_path: str) -> AsyncIterator[bytes]:
        """Downloads a file as a stream of bytes."""
        path = self._get_full_path(file_path)
        if not await aiofiles.os.path.exists(path):
            raise FileNotFoundError(f"File not found at {file_path}")

        async with aiofiles.open(path, "rb") as f:
            while chunk := await f.read(8192):  # 8KB chunks
                yield chunk

    async def upload_file(self, file_path: str, data: bytes) -> None:
        """Uploads data to a file."""
        path = self._get_full_path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "wb") as f:
            await f.write(data)

    async def delete_file(self, file_path: str) -> None:
        """Deletes a file."""
        path = self._get_full_path(file_path)
        if await aiofiles.os.path.exists(path):
            await aiofiles.os.remove(path)

    async def list_files(self, prefix: str) -> AsyncIterator[str]:
        """Lists keys beginning with `prefix`.

        `prefix` is a string prefix on the key, not a directory: `list_files("doc")`
        yields both `doc.txt` and `docs/a.txt`. This mirrors S3's `list_objects_v2`, so
        swapping providers does not change what a caller gets back.
        """

        def _walk_sync() -> list[str]:
            keys = (p.relative_to(self.root_path).as_posix() for p in self.root_path.rglob("*") if p.is_file())
            return sorted(key for key in keys if key.startswith(prefix))

        for key in await asyncio.to_thread(_walk_sync):
            yield key

    async def file_exists(self, file_path: str) -> bool:
        """Checks if a file exists. Raises ValueError if the key escapes the storage root."""
        path = self._get_full_path(file_path)
        return await aiofiles.os.path.exists(path)

    async def get_file_metadata(self, file_path: str) -> dict[str, Any]:
        """Gets metadata for a file.

        `size`, `last_modified` (UTC datetime) and `path` are the keys every provider
        guarantees; see `FileStorageClient.get_file_metadata`.
        """
        path = self._get_full_path(file_path)
        if not await aiofiles.os.path.exists(path):
            raise FileNotFoundError(f"File not found at {file_path}")

        stat = await aiofiles.os.stat(path)
        return {
            "size": stat.st_size,
            # A UTC datetime, matching S3's LastModified -- st_mtime is a float, and a
            # caller must not have to ask which provider it is talking to.
            "last_modified": datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.UTC),
            "path": path.relative_to(self.root_path).as_posix(),
        }
