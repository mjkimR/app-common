# app-file-storage

A standalone object-storage adapter exposing one async interface (`FileStorageClient`) over multiple backends. Ships with a Local filesystem provider and an S3-compatible provider (AWS S3 / MinIO).

## Installation

```bash
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=app-file-storage"
```

## Configuration

Select the backend with `FS_PROVIDER`, then set the provider-specific variables.

| Variable | Default | Description |
|---|---|---|
| `FS_PROVIDER` | `none` | Backend to use: `none` \| `local` \| `s3` |

**Local (`FS_PROVIDER=local`)**

| Variable | Default | Description |
|---|---|---|
| `FS_LOCAL_BUCKET_NAME` | — | Base directory used as the storage root |

**S3 / MinIO (`FS_PROVIDER=s3`)**

| Variable | Default | Description |
|---|---|---|
| `FS_S3_ENDPOINT_URL` | — | S3 endpoint (omit for AWS, set for MinIO) |
| `FS_S3_ACCESS_KEY` | — | Access key ID |
| `FS_S3_SECRET_KEY` | — | Secret access key |
| `FS_S3_BUCKET_NAME` | `my-bucket` | Target bucket |
| `FS_S3_REGION_NAME` | `None` | Region (optional) |
| `FS_S3_AUTO_CREATE_BUCKET` | `false` | Create the bucket at startup if missing |

## Usage

Wire the lifespan into your FastAPI app, then resolve the client:

```python
from fastapi import FastAPI
from app_file_storage import get_storage_client, lifespan_file_storage

app = FastAPI(lifespan=lifespan_file_storage)


async def save(data: bytes):
    client = get_storage_client()
    await client.upload_file("reports/2026.pdf", data)
    return await client.file_exists("reports/2026.pdf")
```

## Interface

`FileStorageClient` (async): `upload_file`, `download_file`, `download_file_stream`, `delete_file`, `list_files`, `file_exists`, `get_file_metadata`, `close`. Object versioning is supported on S3 (`version_id` on `download_file`) and raises `NotImplementedError` on Local.

## Public API

- `FileStorageClient` — the provider-agnostic interface
- `get_storage_client()` — the initialized client singleton
- `lifespan_file_storage` — FastAPI lifespan that builds and closes the client

## See also

- [Adapter Module Reference](../skill/app-base-developer-skill/docs/reference_adapter.md) — shared adapter conventions and index.
- [Architecture & Service Hooks Guide](../skill/app-base-developer-skill/docs/app_layer_base_guide.md) — how adapters fit the layered app.
