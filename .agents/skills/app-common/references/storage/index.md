# app-file-storage

Asynchronous object storage client (`FileStorageClient`) with interchangeable backends (AWS S3, MinIO, Local FS).

> For package installation and environment variables, see [setup.md](./setup.md).

## Lifespan Wiring

```python
from fastapi import FastAPI
from app_file_storage import lifespan_file_storage

app = FastAPI(lifespan=lifespan_file_storage)
```

## Usage

```python
from app_file_storage import get_storage_client


async def save_file(filename: str, data: bytes):
    client = get_storage_client()
    await client.upload_file(filename, data)
    return await client.file_exists(filename)


async def read_file(filename: str) -> bytes:
    client = get_storage_client()
    return await client.download_file(filename)


async def remove_file(filename: str):
    client = get_storage_client()
    await client.delete_file(filename)
```

## Canonical local paths

For application-owned filesystem paths, import `atomic_write`, `atomic_copy`,
`atomic_write_stream`, `atomic_writer` and `file_hash` from
`app_file_storage.local_files`. Writes flush/fsync a sibling temporary file before
atomic replacement; streaming failures preserve the old destination. The caller
owns path validation, writer locks and multi-file rollback. These synchronous
helpers do not promise power-loss recovery. Async applications must drain worker
threads before releasing resource scopes (see `run_blocking` in the backend guide).
