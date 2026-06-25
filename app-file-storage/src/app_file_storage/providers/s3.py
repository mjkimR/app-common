from collections.abc import AsyncIterator
from typing import Any

import aiobotocore.session
from aiobotocore.client import AioBaseClient
from botocore.exceptions import ClientError
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app_file_storage.interface import FileStorageClient


class S3FileStorageSettings(BaseSettings):
    """Settings for when the file storage provider is 's3'."""

    endpoint_url: str = Field(
        default="http://localhost:9000", description="S3-compatible endpoint URL (e.g. MinIO or AWS S3)"
    )
    access_key: SecretStr = Field(description="S3 access key ID for authentication")
    secret_key: SecretStr = Field(description="S3 secret access key for authentication")
    bucket_name: str = Field(default="my-bucket", description="Name of the S3 bucket to use for file storage")
    region_name: str | None = Field(
        default=None, description="AWS region name (required for AWS S3, optional for S3-compatible providers)"
    )
    auto_create_bucket: bool = Field(
        default=True,
        description="If True, automatically create the bucket on startup if it does not exist",
    )

    model_config = SettingsConfigDict(env_prefix="FS_S3_")


class S3StorageProvider(FileStorageClient):
    """Manages file operations with an S3-compatible storage service."""

    def __init__(self, context: Any, client: AioBaseClient, bucket_name: str):
        self.context = context
        # Typed as Any to bypass Pyright errors from aiobotocore's dynamically generated methods
        self.client: Any = client
        self.bucket_name = bucket_name

    @classmethod
    async def from_env(cls) -> "S3StorageProvider":
        """
        Creates the S3 client from configuration and returns it with the bucket name.

        If FS_S3_AUTO_CREATE_BUCKET=true, the bucket is created when it does not exist.
        Otherwise a RuntimeError is raised if the bucket is missing.
        """
        config = S3FileStorageSettings()  # type: ignore
        session = aiobotocore.session.get_session()
        context = session.create_client(
            "s3",
            aws_access_key_id=config.access_key.get_secret_value(),
            aws_secret_access_key=config.secret_key.get_secret_value(),
            region_name=config.region_name,
            endpoint_url=config.endpoint_url,
        )
        client = await context.__aenter__()
        instance = cls(context, client, config.bucket_name)
        await instance._ensure_bucket(auto_create=config.auto_create_bucket, region_name=config.region_name)
        return instance

    async def _ensure_bucket(self, *, auto_create: bool, region_name: str | None) -> None:
        """
        Verifies that the configured bucket exists.

        If auto_create is True and the bucket is absent, it is created.
        If auto_create is False and the bucket is absent, a RuntimeError is raised.
        """
        try:
            await self.client.head_bucket(Bucket=self.bucket_name)
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code not in ("404", "NoSuchBucket"):
                raise
            if not auto_create:
                raise RuntimeError(
                    f"S3 bucket '{self.bucket_name}' does not exist. "
                    "Set FS_S3_AUTO_CREATE_BUCKET=true to create it automatically."
                ) from e
            create_kwargs: dict[str, Any] = {"Bucket": self.bucket_name}
            if region_name and region_name != "us-east-1":
                create_kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region_name}
            await self.client.create_bucket(**create_kwargs)

    async def close(self) -> None:
        """Closes the S3 client context."""
        await self.context.__aexit__(None, None, None)

    async def download_file(self, file_path: str, version_id: str | None = None) -> bytes:
        """Downloads a file from S3 and returns its content as bytes."""

        try:
            kwargs = {"Bucket": self.bucket_name, "Key": file_path}
            if version_id:
                kwargs["VersionId"] = version_id
            response = await self.client.get_object(**kwargs)
            async with response["Body"] as stream:
                return await stream.read()
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"File not found at {file_path}") from e
            raise

    async def download_file_stream(self, file_path: str) -> AsyncIterator[bytes]:
        """Downloads a file from S3 as a stream of bytes."""

        try:
            response = await self.client.get_object(Bucket=self.bucket_name, Key=file_path)
            async for chunk in response["Body"].iter_chunks(chunk_size=8192):
                yield chunk
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"File not found at {file_path}") from e
            raise

    async def upload_file(self, file_path: str, data: bytes) -> None:
        """Uploads data to a file in S3."""
        await self.client.put_object(Bucket=self.bucket_name, Key=file_path, Body=data)

    async def delete_file(self, file_path: str) -> None:
        """Deletes a file from S3."""
        await self.client.delete_object(Bucket=self.bucket_name, Key=file_path)

    async def list_files(self, prefix: str) -> AsyncIterator[str]:
        """Lists files in S3 matching a given prefix."""
        paginator = self.client.get_paginator("list_objects_v2")
        async for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
            if "Contents" in page:
                for obj in page["Contents"]:
                    yield obj["Key"]

    async def file_exists(self, file_path: str) -> bool:
        """Checks if a file exists in S3."""
        try:
            await self.client.head_object(Bucket=self.bucket_name, Key=file_path)
            return True
        except ClientError:
            return False

    async def get_file_metadata(self, file_path: str) -> dict[str, Any]:
        """Gets metadata for a file from S3."""

        try:
            metadata = await self.client.head_object(Bucket=self.bucket_name, Key=file_path)
            return {
                "size": metadata.get("ContentLength"),
                "last_modified": metadata.get("LastModified"),
                "content_type": metadata.get("ContentType"),
                "etag": metadata.get("ETag", "").strip('"'),
                "path": file_path,
            }
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                raise FileNotFoundError(f"File not found at {file_path}") from e
            raise
