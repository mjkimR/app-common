import asyncio
from pathlib import Path
from typing import Any, AsyncIterator

import aiofiles
import aiofiles.os
from app_base.config import FileStorageSettings
from app_base.config.file_storage import LocalFileStorageSettings

from app_base.adapter.file_storage.interface import FileStorageClient


class LocalStorageProvider(FileStorageClient):
    """Manages file operations on the local filesystem."""

    def __init__(self, root_path: str | Path):
        self.root_path = Path(root_path)
        if not self.root_path.exists():
            self.root_path.mkdir(parents=True, exist_ok=True)

    @classmethod
    async def from_config(cls, settings: FileStorageSettings[LocalFileStorageSettings]) -> FileStorageClient:
        if not settings.config:
            raise ValueError("Local storage settings are not configured.")
        config: LocalFileStorageSettings = settings.config
        root_path = Path(config.bucket_name)
        root_path.mkdir(parents=True, exist_ok=True)
        return cls(root_path)

    async def close(self) -> None:
        """Local storage does not require a client to be closed."""
        pass

    def _get_full_path(self, file_path: str) -> Path:
        """Resolves the full, absolute path for a file, ensuring it's within the root."""
        full_path = self.root_path.joinpath(file_path).resolve()
        if self.root_path.resolve() not in full_path.parents:
            raise ValueError("File path is outside the allowed storage directory.")
        return full_path

    async def download_file(self, file_path: str) -> bytes:
        """Downloads a file and returns its content as bytes."""
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

    async def list_files(self, prefix: str) -> list[str]:
        """Lists files matching a given prefix (directory path)."""
        search_path = self._get_full_path(prefix)

        def _glob_sync():
            return [str(p.relative_to(self.root_path)) for p in search_path.rglob("*") if p.is_file()]

        return await asyncio.to_thread(_glob_sync)

    async def file_exists(self, file_path: str) -> bool:
        """Checks if a file exists."""
        try:
            path = self._get_full_path(file_path)
            return await aiofiles.os.path.exists(path)
        except ValueError:
            return False

    async def get_file_metadata(self, file_path: str) -> dict[str, Any]:
        """Gets metadata for a file."""
        path = self._get_full_path(file_path)
        if not await aiofiles.os.path.exists(path):
            raise FileNotFoundError(f"File not found at {file_path}")

        stat = await aiofiles.os.stat(path)
        return {
            "size": stat.st_size,
            "last_modified": stat.st_mtime,
            "path": str(path.relative_to(self.root_path)),
        }
