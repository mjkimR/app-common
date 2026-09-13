# app-file-storage Setup & Configuration

## Installation
```bash
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=packages/adapters/app-file-storage"
```

## Configuration

Select the backend with `FS_PROVIDER`:

| Variable | Default | Description |
|---|---|---|
| `FS_PROVIDER` | `none` | Backend to use: `none` \| `local` \| `s3` |

### Local Filesystem (`FS_PROVIDER=local`)
| Variable | Description |
|---|---|
| `FS_LOCAL_BUCKET_NAME` | Base filesystem directory used as the storage root |

### AWS S3 / MinIO (`FS_PROVIDER=s3`)
| Variable | Default | Description |
|---|---|---|
| `FS_S3_BUCKET_NAME` | `my-bucket` | Target bucket name |
| `FS_S3_ACCESS_KEY` | — | Access key ID |
| `FS_S3_SECRET_KEY` | — | Secret access key |
| `FS_S3_ENDPOINT_URL` | — | S3 endpoint URL (omit for AWS S3, specify for MinIO) |
| `FS_S3_REGION_NAME` | `None` | AWS Region (optional) |
| `FS_S3_AUTO_CREATE_BUCKET` | `false` | Automatically create the bucket at startup |
