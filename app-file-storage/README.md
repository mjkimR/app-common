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

`FileStorageClient` (async): `upload_file`, `download_file`, `download_file_stream`, `delete_file`, `list_files`, `file_exists`, `get_file_metadata`, `close`.

Providers are swappable, so the contract holds for every one of them — `tests/integrate/test_contract.py` runs the same assertions against Local and a real S3:

- **Keys are opaque strings, S3-style.** `a/b.txt` is a key, not a directory, and a key can never address anything outside the bucket/root — `../` raises `ValueError`.
- **`list_files(prefix)` matches on the string prefix of the key**, so `list_files("doc")` yields both `doc.txt` and `docs/a.txt`.
- **Missing key → `FileNotFoundError`** from `download_file`, `download_file_stream` and `get_file_metadata`. `delete_file` on a missing key is a no-op.
- **`file_exists` returns `False` only for a genuine not-found.** Denied credentials or an unreachable backend raise — absence and failure are never conflated.
- **`get_file_metadata` always returns `size` (int), `last_modified` (timezone-aware `datetime`) and `path`.** S3 adds `content_type` and `etag`.

Object versioning is S3-only (`version_id` on `download_file`); Local raises `NotImplementedError`. It also needs versioning enabled **on the bucket** — this package never turns it on, so without it `put_object` returns no version to ask for.

## Testing

```bash
just test          # unit + the local-filesystem half of the contract suite. No Docker.
just test-docker   # ...plus the S3 half, against a real MinIO. Needs Docker.
```

The S3 tests are marked `docker` and deselected by default, so the everyday run stays fast. **CI runs `just test-docker` on every push**, so they are still verified before anything merges — deselecting them locally is a convenience, not a gap.

Mocked aiobotocore hid three real bugs here (a path-traversal hole, a crash on the default config, and denied credentials being reported as "file not found"), all while the code was 100% line-covered. That is what these run against a real backend for.

## Public API

- `FileStorageClient` — the provider-agnostic interface
- `get_storage_client()` — the initialized client singleton
- `lifespan_file_storage` — FastAPI lifespan that builds and closes the client

## See also

- [Adapter Module Reference](../skill/app-base-developer-skill/docs/reference_adapter.md) — shared adapter conventions and index.
- [Architecture & Service Hooks Guide](../skill/app-base-developer-skill/docs/app_layer_base_guide.md) — how adapters fit the layered app.
