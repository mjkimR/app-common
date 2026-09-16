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
from app_file_storage import get_file_storage_client


async def save_file(filename: str, data: bytes):
    client = get_file_storage_client()
    await client.upload_file(file_data=data, file_name=filename, content_type="application/octet-stream")
    return await client.get_presigned_url(file_name=filename, expiration=3600)


async def read_file(filename: str) -> bytes:
    client = get_file_storage_client()
    return await client.download_file(file_name=filename)


async def remove_file(filename: str):
    client = get_file_storage_client()
    await client.delete_file(file_name=filename)
```
