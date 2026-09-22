"""S3 behaviour a mocked aiobotocore cannot vouch for.

The provider branches on error-code strings it gets back from S3 (`NoSuchKey` here,
`404` there). Against an `AsyncMock` those strings are whatever the test asserts they
are, which proves nothing. These pin them to what a real S3 sends.
"""

import asyncio

import pytest
from app_file_storage.providers.s3 import S3StorageProvider
from botocore.exceptions import ClientError

from .conftest import s3_client


class TestErrorCodesAreWhatTheProviderExpects:
    """`get_object` and `head_object` report a missing key differently. Both are handled."""

    async def test_get_object_reports_a_missing_key_as_NoSuchKey(self, minio_endpoint, bucket):
        async with s3_client(minio_endpoint) as client:
            with pytest.raises(ClientError) as exc:
                await client.get_object(Bucket=bucket, Key="nope.txt")

        assert exc.value.response["Error"]["Code"] == "NoSuchKey"

    async def test_head_object_reports_a_missing_key_as_404(self, minio_endpoint, bucket):
        async with s3_client(minio_endpoint) as client:
            with pytest.raises(ClientError) as exc:
                await client.head_object(Bucket=bucket, Key="nope.txt")

        assert exc.value.response["Error"]["Code"] == "404"

    async def test_head_bucket_reports_a_missing_bucket_as_404(self, minio_endpoint):
        async with s3_client(minio_endpoint) as client:
            with pytest.raises(ClientError) as exc:
                await client.head_bucket(Bucket="no-such-bucket-here")

        assert exc.value.response["Error"]["Code"] == "404"


class TestFileExistsDoesNotSwallowFailures:
    """`file_exists` used to `except ClientError: return False`.

    With credentials that cannot read the bucket, S3 answers 403 -- and the provider
    reported that as "the file isn't there". A caller would then happily overwrite data it
    could not see, or report a missing file to a user, when the real fault was config.
    """

    async def test_denied_credentials_raise_instead_of_reporting_absence(self, minio_endpoint, bucket, s3_provider):
        await s3_provider.upload_file("real.txt", b"i am here")
        assert await s3_provider.file_exists("real.txt") is True

        async with s3_client(minio_endpoint, access_key="wrong", secret_key="alsowrong") as bad_client:
            denied = S3StorageProvider(context=None, client=bad_client, bucket_name=bucket)

            with pytest.raises(ClientError) as exc:
                await denied.file_exists("real.txt")

        assert exc.value.response["Error"]["Code"] == "403"


class TestEnsureBucket:
    async def test_creates_the_bucket_when_auto_create_is_on(self, minio_endpoint):
        async with s3_client(minio_endpoint) as client:
            provider = S3StorageProvider(context=None, client=client, bucket_name="auto-created-bucket")

            await provider._ensure_bucket(auto_create=True, region_name=None)

            await client.head_bucket(Bucket="auto-created-bucket")  # raises if absent
            await client.delete_bucket(Bucket="auto-created-bucket")

    async def test_raises_a_clear_error_when_auto_create_is_off(self, minio_endpoint):
        async with s3_client(minio_endpoint) as client:
            provider = S3StorageProvider(context=None, client=client, bucket_name="absent-bucket")

            with pytest.raises(RuntimeError, match="FS_S3_AUTO_CREATE_BUCKET"):
                await provider._ensure_bucket(auto_create=False, region_name=None)

    async def test_is_a_no_op_when_the_bucket_already_exists(self, s3_provider):
        await s3_provider.upload_file("keep.txt", b"keep")

        await s3_provider._ensure_bucket(auto_create=True, region_name=None)

        assert await s3_provider.download_file("keep.txt") == b"keep"


class TestVersioning:
    """`download_file(version_id=...)` only works on a bucket with versioning enabled.

    Nothing in the provider turns versioning on, so this is a capability of the bucket a
    deployment supplies, not of the client. Without it, `put_object` returns no VersionId
    at all and there is nothing to pass back in.
    """

    async def test_without_versioning_there_is_no_version_to_ask_for(self, minio_endpoint, bucket):
        async with s3_client(minio_endpoint) as client:
            response = await client.put_object(Bucket=bucket, Key="v.txt", Body=b"only")

        assert response.get("VersionId") is None

    async def test_an_old_version_is_still_readable_once_versioning_is_on(self, minio_endpoint, bucket, s3_provider):
        async with s3_client(minio_endpoint) as client:
            await client.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
            first = await client.put_object(Bucket=bucket, Key="v.txt", Body=b"OLD")
            await client.put_object(Bucket=bucket, Key="v.txt", Body=b"NEW")

        assert await s3_provider.download_file("v.txt") == b"NEW"
        assert await s3_provider.download_file("v.txt", version_id=first["VersionId"]) == b"OLD"


class TestListFilesPagination:
    async def test_paginates_past_the_1000_key_limit(self, minio_endpoint, bucket, s3_provider):
        """S3 caps `list_objects_v2` at 1000 keys per page, so the provider paginates.

        A mock returning one page can never show whether that works; this is the only way
        to find out that key 1001 comes back.
        """
        total = 1050

        async with s3_client(minio_endpoint) as client:
            for start in range(0, total, 100):
                await asyncio.gather(
                    *(
                        client.put_object(Bucket=bucket, Key=f"page/{i:05d}.txt", Body=b"x")
                        for i in range(start, min(start + 100, total))
                    )
                )

        keys = [key async for key in s3_provider.list_files("page/")]

        assert len(keys) == total, "an unpaginated listing would have stopped at 1000"
        assert keys[-1] == f"page/{total - 1:05d}.txt"
