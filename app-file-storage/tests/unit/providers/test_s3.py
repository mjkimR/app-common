from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app_file_storage.config import FileStorageSettings, S3FileStorageSettings
from app_file_storage.providers.s3 import S3StorageProvider
from botocore.exceptions import ClientError
from pydantic import SecretStr


@pytest.fixture
def mock_s3_settings():
    mock_settings = MagicMock(spec=FileStorageSettings)
    mock_settings.provider = "s3"
    mock_settings.config = S3FileStorageSettings(
        bucket_name="test-bucket",
        access_key=SecretStr("test_access_key"),
        secret_key=SecretStr("test_secret_key"),
        region_name="us-east-1",
        endpoint_url="http://localhost:9000",
    )
    return mock_settings


@pytest.fixture
def mock_s3_settings_no_api_key():
    mock_settings = MagicMock(spec=FileStorageSettings)
    mock_settings.provider = "s3"
    mock_settings.config = S3FileStorageSettings(
        bucket_name="test-bucket",
        access_key=None,  # type: ignore
        secret_key=None,  # type: ignore
        region_name="us-east-1",
        endpoint_url="http://localhost:9000",
    )
    return mock_settings


@pytest.fixture
def mock_aiobotocore_client():
    mock_client = AsyncMock()
    mock_client.close = AsyncMock()

    # This is the object that `paginator.paginate()` should return, and it should be async iterable.
    mock_paginate_result_iterable = MagicMock()
    mock_paginate_result_iterable.__aiter__.return_value = [
        {"Contents": [{"Key": "file1.txt"}, {"Key": "subdir/file2.txt"}]}
    ]

    # The paginate method itself: it should *directly* return the iterable, not a coroutine.
    # So, we'll make it a simple MagicMock that returns mock_paginate_result_iterable
    mock_paginate_method = MagicMock(return_value=mock_paginate_result_iterable)

    # Mock the paginator instance that get_paginator returns
    mock_paginator_instance = MagicMock()
    mock_paginator_instance.paginate = mock_paginate_method  # Set the paginate method

    # Configure mock_client.get_paginator to return the mock_paginator_instance
    mock_client.get_paginator = MagicMock(return_value=mock_paginator_instance)

    return mock_client


async def test_from_config_success(mock_s3_settings, mock_aiobotocore_client):
    with patch("aiobotocore.session.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_session.create_client.return_value.__aenter__.return_value = mock_aiobotocore_client
        mock_get_session.return_value = mock_session

        provider = await S3StorageProvider.from_config(mock_s3_settings)

        mock_get_session.assert_called_once()
        mock_session.create_client.assert_called_once_with(
            "s3",
            aws_access_key_id="test_access_key",
            aws_secret_access_key="test_secret_key",
            region_name="us-east-1",
            endpoint_url="http://localhost:9000",
        )
        assert provider.client == mock_aiobotocore_client
        assert provider.bucket_name == "test-bucket"


async def test_from_config_no_config_raises_error():
    mock_settings = MagicMock(spec=FileStorageSettings)
    mock_settings.provider = "s3"
    mock_settings.config = None  # Set config to None for this test case
    with pytest.raises(ValueError, match=r"S3 storage settings are not configured."):
        await S3StorageProvider.from_config(mock_settings)


async def test_close(mock_aiobotocore_client):
    provider = S3StorageProvider(mock_aiobotocore_client, "test-bucket")
    await provider.close()
    mock_aiobotocore_client.close.assert_called_once()


async def test_download_file_success(mock_aiobotocore_client):
    mock_body_stream = AsyncMock()
    mock_body_stream.read.return_value = b"file content"

    # Mock the async context manager behavior
    mock_body = AsyncMock()
    mock_body.__aenter__.return_value = mock_body_stream
    mock_body.__aexit__.return_value = None

    mock_aiobotocore_client.get_object.return_value = {"Body": mock_body}
    provider = S3StorageProvider(mock_aiobotocore_client, "test-bucket")
    content = await provider.download_file("test.txt")
    mock_aiobotocore_client.get_object.assert_called_once_with(Bucket="test-bucket", Key="test.txt")
    assert content == b"file content"


async def test_download_file_not_found(mock_aiobotocore_client):
    mock_aiobotocore_client.get_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}, "GetObject"
    )
    provider = S3StorageProvider(mock_aiobotocore_client, "test-bucket")
    with pytest.raises(FileNotFoundError, match=r"File not found at non_existent.txt"):
        await provider.download_file("non_existent.txt")


async def test_download_file_stream_success(mock_aiobotocore_client):
    mock_body = MagicMock()
    mock_body.iter_chunks.return_value.__aiter__.return_value = [b"chunk1", b"chunk2"]
    mock_aiobotocore_client.get_object.return_value = {"Body": mock_body}

    provider = S3StorageProvider(mock_aiobotocore_client, "test-bucket")
    chunks = [chunk async for chunk in provider.download_file_stream("test.txt")]
    assert chunks == [b"chunk1", b"chunk2"]


async def test_download_file_stream_not_found(mock_aiobotocore_client):
    mock_aiobotocore_client.get_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}, "GetObject"
    )
    provider = S3StorageProvider(mock_aiobotocore_client, "test-bucket")
    with pytest.raises(FileNotFoundError, match=r"File not found at non_existent.txt"):
        async for _ in provider.download_file_stream("non_existent.txt"):
            pass


async def test_upload_file_success(mock_aiobotocore_client):
    provider = S3StorageProvider(mock_aiobotocore_client, "test-bucket")
    await provider.upload_file("upload.txt", b"upload data")
    mock_aiobotocore_client.put_object.assert_called_once_with(
        Bucket="test-bucket", Key="upload.txt", Body=b"upload data"
    )


async def test_delete_file_success(mock_aiobotocore_client):
    provider = S3StorageProvider(mock_aiobotocore_client, "test-bucket")
    await provider.delete_file("delete.txt")
    mock_aiobotocore_client.delete_object.assert_called_once_with(Bucket="test-bucket", Key="delete.txt")


async def test_list_files_success(mock_aiobotocore_client):
    provider = S3StorageProvider(mock_aiobotocore_client, "test-bucket")
    files = await provider.list_files("prefix/")
    mock_aiobotocore_client.get_paginator.assert_called_once_with("list_objects_v2")
    mock_aiobotocore_client.get_paginator.return_value.paginate.assert_called_once_with(
        Bucket="test-bucket", Prefix="prefix/"
    )
    assert files == ["file1.txt", "subdir/file2.txt"]


async def test_file_exists_true(mock_aiobotocore_client):
    mock_aiobotocore_client.head_object.return_value = {}
    provider = S3StorageProvider(mock_aiobotocore_client, "test-bucket")
    exists = await provider.file_exists("existing.txt")
    assert exists is True


async def test_file_exists_false(mock_aiobotocore_client):
    mock_aiobotocore_client.head_object.side_effect = ClientError(
        {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject"
    )
    provider = S3StorageProvider(mock_aiobotocore_client, "test-bucket")
    exists = await provider.file_exists("non_existing.txt")
    assert exists is False


async def test_get_file_metadata_success(mock_aiobotocore_client):
    mock_aiobotocore_client.head_object.return_value = {
        "ContentLength": 123,
        "LastModified": "Thu, 01 Jan 1970 00:00:00 GMT",
        "ContentType": "text/plain",
        "ETag": '"abc"',
    }
    provider = S3StorageProvider(mock_aiobotocore_client, "test-bucket")
    metadata = await provider.get_file_metadata("meta.txt")
    assert metadata["size"] == 123
    assert metadata["last_modified"] == "Thu, 01 Jan 1970 00:00:00 GMT"
    assert metadata["content_type"] == "text/plain"
    assert metadata["etag"] == "abc"
    assert metadata["path"] == "meta.txt"


async def test_get_file_metadata_not_found(mock_aiobotocore_client):
    mock_aiobotocore_client.head_object.side_effect = ClientError(
        {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject"
    )
    provider = S3StorageProvider(mock_aiobotocore_client, "test-bucket")
    with pytest.raises(FileNotFoundError, match=r"File not found at non_existent_meta.txt"):
        await provider.get_file_metadata("non_existent_meta.txt")
