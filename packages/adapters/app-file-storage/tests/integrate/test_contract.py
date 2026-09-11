"""The FileStorageClient contract, enforced against every real implementation.

Each test here runs twice -- once on the local filesystem, once on a real S3 (MinIO).
A provider is meant to be swappable, so any behaviour that differs between the two is a
bug in one of them, and this file is where that shows up.

Every bug these caught on the way in is marked with the assertion that catches it.
"""

import datetime
from pathlib import Path

import pytest
from app_file_storage.providers.local import LocalStorageProvider


async def _keys(provider, prefix: str = "") -> list[str]:
    return sorted([key async for key in provider.list_files(prefix)])


class TestRoundTrip:
    async def test_upload_then_download_returns_the_same_bytes(self, provider):
        await provider.upload_file("hello.txt", b"hello world")
        assert await provider.download_file("hello.txt") == b"hello world"

    async def test_upload_overwrites(self, provider):
        await provider.upload_file("k.txt", b"first")
        await provider.upload_file("k.txt", b"second")
        assert await provider.download_file("k.txt") == b"second"

    async def test_nested_key_round_trips(self, provider):
        await provider.upload_file("a/b/c.txt", b"deep")
        assert await provider.download_file("a/b/c.txt") == b"deep"
        assert await provider.file_exists("a/b/c.txt")

    async def test_empty_file_round_trips(self, provider):
        await provider.upload_file("empty.txt", b"")
        assert await provider.download_file("empty.txt") == b""
        assert await provider.file_exists("empty.txt")

    async def test_binary_payload_survives(self, provider):
        blob = bytes(range(256)) * 8
        await provider.upload_file("blob.bin", blob)
        assert await provider.download_file("blob.bin") == blob

    async def test_download_stream_reassembles_the_payload(self, provider):
        # Larger than the 8 KiB chunk size, so this actually spans several chunks.
        blob = b"".join(bytes([i % 256]) for i in range(20_000))
        await provider.upload_file("big.bin", blob)

        chunks = [chunk async for chunk in provider.download_file_stream("big.bin")]

        assert len(chunks) > 1, "expected the payload to arrive in multiple chunks"
        assert b"".join(chunks) == blob


class TestDelete:
    async def test_delete_removes_the_file(self, provider):
        await provider.upload_file("gone.txt", b"x")
        await provider.delete_file("gone.txt")
        assert not await provider.file_exists("gone.txt")

    async def test_deleting_a_missing_file_is_a_no_op(self, provider):
        await provider.delete_file("never-existed.txt")  # must not raise


class TestMissingKey:
    async def test_download_raises_file_not_found(self, provider):
        with pytest.raises(FileNotFoundError):
            await provider.download_file("nope.txt")

    async def test_download_stream_raises_file_not_found(self, provider):
        with pytest.raises(FileNotFoundError):
            [chunk async for chunk in provider.download_file_stream("nope.txt")]

    async def test_get_file_metadata_raises_file_not_found(self, provider):
        with pytest.raises(FileNotFoundError):
            await provider.get_file_metadata("nope.txt")

    async def test_file_exists_is_false(self, provider):
        assert await provider.file_exists("nope.txt") is False


class TestListFiles:
    """`prefix` is a string prefix on the key, not a directory.

    The local provider used to rglob inside `prefix` as a directory, so `list_files("doc")`
    returned nothing while S3 returned both `doc.txt` and `docs/a.txt` -- the same call,
    different answers, depending on which provider was configured.
    """

    @pytest.fixture(autouse=True)
    async def _seed(self, provider):
        await provider.upload_file("doc.txt", b"1")
        await provider.upload_file("docs/a.txt", b"2")
        await provider.upload_file("docs/sub/b.txt", b"3")
        await provider.upload_file("other.txt", b"4")

    async def test_prefix_is_a_string_prefix_not_a_directory(self, provider):
        assert await _keys(provider, "doc") == ["doc.txt", "docs/a.txt", "docs/sub/b.txt"]

    async def test_prefix_can_still_name_a_directory(self, provider):
        assert await _keys(provider, "docs/") == ["docs/a.txt", "docs/sub/b.txt"]

    async def test_empty_prefix_lists_everything_recursively(self, provider):
        assert await _keys(provider, "") == ["doc.txt", "docs/a.txt", "docs/sub/b.txt", "other.txt"]

    async def test_unmatched_prefix_is_empty(self, provider):
        assert await _keys(provider, "zzz") == []

    async def test_deleted_files_leave_the_listing(self, provider):
        await provider.delete_file("docs/a.txt")
        assert await _keys(provider, "docs") == ["docs/sub/b.txt"]


class TestMetadata:
    async def test_guarantees_size_last_modified_and_path(self, provider):
        await provider.upload_file("m.txt", b"12345")

        md = await provider.get_file_metadata("m.txt")

        assert md["size"] == 5
        assert md["path"] == "m.txt"
        # `last_modified` was a float (st_mtime) on local and a datetime on S3, so
        # `md["last_modified"].isoformat()` worked on one provider and crashed on the other.
        assert isinstance(md["last_modified"], datetime.datetime)
        assert md["last_modified"].tzinfo is not None, "last_modified must be timezone-aware"

    async def test_size_reflects_an_overwrite(self, provider):
        await provider.upload_file("m.txt", b"12345")
        await provider.upload_file("m.txt", b"1")
        assert (await provider.get_file_metadata("m.txt"))["size"] == 1


class TestKeysCannotEscapeTheRoot:
    """A key must not address anything outside the bucket/root.

    The local provider joined the key onto the root and resolved it, so `../secret.txt`
    read, overwrote and deleted arbitrary files on the host. An S3 key cannot leave its
    bucket, and neither may a local one.
    """

    @pytest.mark.parametrize("key", ["../escaped.txt", "a/../../escaped.txt", "../../etc/passwd"])
    async def test_upload_outside_the_root_is_refused(self, local_provider, key):
        with pytest.raises(ValueError, match="escapes the storage root"):
            await local_provider.upload_file(key, b"ESCAPED")

    async def test_download_outside_the_root_is_refused(self, local_provider, tmp_path):
        secret = tmp_path / "secret.txt"
        secret.write_text("SENSITIVE")

        with pytest.raises(ValueError, match="escapes the storage root"):
            await local_provider.download_file("../secret.txt")

        assert secret.read_text() == "SENSITIVE"

    async def test_delete_outside_the_root_is_refused(self, local_provider, tmp_path):
        secret = tmp_path / "secret.txt"
        secret.write_text("SENSITIVE")

        with pytest.raises(ValueError, match="escapes the storage root"):
            await local_provider.delete_file("../secret.txt")

        assert secret.exists(), "delete must not reach outside the storage root"

    async def test_a_key_that_merely_looks_like_traversal_is_fine(self, local_provider):
        await local_provider.upload_file("a/b/../c.txt", b"ok")  # normalises to a/c.txt
        assert await local_provider.download_file("a/c.txt") == b"ok"


class TestLocalRootIsNormalised:
    """The root the provider is *given* is not always the root it can work with.

    `_get_full_path` resolves every key, so an unresolved root made `relative_to` in
    `list_files` raise ValueError. It went unnoticed because the tests only ever passed
    `tmp_path`, which is already absolute and symlink-free -- while `from_env()` builds
    `Path(settings.bucket_name)`, a *relative* path, and broke on the default config.
    """

    async def test_works_with_the_relative_root_that_from_env_builds(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        provider = LocalStorageProvider(Path("local_storage"))  # exactly what from_env() passes

        await provider.upload_file("docs/a.txt", b"x")

        assert await _keys(provider, "docs") == ["docs/a.txt"]
        assert await provider.download_file("docs/a.txt") == b"x"
        assert (await provider.get_file_metadata("docs/a.txt"))["path"] == "docs/a.txt"

    async def test_works_with_an_absolute_root_behind_a_symlink(self, tmp_path):
        real = tmp_path / "real"
        real.mkdir()
        link = tmp_path / "link"
        link.symlink_to(real, target_is_directory=True)

        provider = LocalStorageProvider(link / "storage")

        await provider.upload_file("docs/a.txt", b"x")

        assert await _keys(provider, "docs") == ["docs/a.txt"]

    async def test_from_env_produces_a_usable_provider(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("FS_LOCAL_BUCKET_NAME", "from_env_storage")

        provider = await LocalStorageProvider.from_env()

        await provider.upload_file("docs/a.txt", b"x")
        assert await _keys(provider, "docs") == ["docs/a.txt"]
