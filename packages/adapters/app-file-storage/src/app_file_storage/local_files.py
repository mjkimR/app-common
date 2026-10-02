"""Local filesystem primitives, independent of resource and sidecar schemas.

Replacement is atomic for one file. Callers own locks and multi-file rollback;
these helpers do not promise a transaction across files or power-loss recovery.
"""

import hashlib
import os
import shutil
import tempfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@contextmanager
def atomic_writer(path: Path) -> Iterator[BinaryIO]:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".app-storage-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            yield stream
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_write(path: Path, data: bytes) -> None:
    with atomic_writer(path) as stream:
        stream.write(data)


def atomic_copy(source: Path, target: Path) -> None:
    """Copy in bounded chunks, publishing only a complete, flushed file."""
    with source.open("rb") as source_stream, atomic_writer(target) as target_stream:
        shutil.copyfileobj(source_stream, target_stream, length=1024 * 1024)


def atomic_write_stream(path: Path, chunks: Iterable[bytes]) -> None:
    """Consume bounded chunks and publish only after iteration and flush succeed."""
    with atomic_writer(path) as stream:
        for chunk in chunks:
            stream.write(chunk)
