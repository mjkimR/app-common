from typing import Any, AsyncIterator

import aiobotocore.session
from aiobotocore.client import AioBaseClient
from botocore.exceptions import ClientError
from config import FileStorageSettings
from config.file_storage import S3FileStorageSettings

from app_base.adapter.file_storage.interface import FileStorageClient


class S3StorageProvider(FileStorageClient):
    """Manages file operations with an S3-compatible storage service."""

    def __init__(self, client: AioBaseClient, bucket_name: str):
        self.client = client
        self.bucket_name = bucket_name

    @classmethod
    async def from_config(cls, settings: FileStorageSettings[S3FileStorageSettings]) -> "S3StorageProvider":
        """
        Creates the S3 client from configuration and returns it with the bucket name.
        """
        if not settings.config:
            raise ValueError("S3 storage settings are not configured.")
        config: S3FileStorageSettings = settings.config
        session = aiobotocore.session.get_session()
        client = await session.create_client(
            "s3",
            aws_access_key_id=config.access_key.get_secret_value(),
            aws_secret_access_key=config.secret_key.get_secret_value(),
            region_name=config.region_name,
            endpoint_url=config.endpoint_url,
        )
        return cls(client, config.bucket_name)

    async def close(self) -> None:
        """
        Closes the S3 client.
        """
        await self.client.close()

    async def download_file(self, file_path: str) -> bytes:
        """Downloads a file from S3 and returns its content as bytes."""

        try:
            response = await self.client.get_object(Bucket=self.bucket_name, Key=file_path)
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

    async def list_files(self, prefix: str) -> list[str]:
        """Lists files in S3 matching a given prefix."""

        paginator = self.client.get_paginator("list_objects_v2")
        file_list = []
        async for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
            if "Contents" in page:
                for obj in page["Contents"]:
                    file_list.append(obj["Key"])
        return file_list

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
