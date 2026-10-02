"""Publication failures never replace the original or leave a staged file."""

import pytest
from app_file_storage import local_files


@pytest.mark.parametrize("operation", ["write", "copy"])
def test_failed_publication_keeps_original(tmp_path, monkeypatch, operation):
    target = tmp_path / "saved.txt"
    target.write_bytes(b"original")
    source = tmp_path / "source.txt"
    source.write_bytes(b"new content")

    def fail(*args):
        raise OSError("replace failed")

    monkeypatch.setattr(local_files.os, "replace", fail)
    with pytest.raises(OSError, match="replace failed"):
        if operation == "write":
            local_files.atomic_write(target, b"replacement")
        else:
            local_files.atomic_copy(source, target)
    assert target.read_bytes() == b"original"
    assert not list(tmp_path.glob(".app-storage-*"))


def test_partial_copy_is_not_published(tmp_path, monkeypatch):
    source, target = tmp_path / "source", tmp_path / "target"
    source.write_bytes(b"source bytes")

    def fail(source, target, **kwargs):
        target.write(source.read(3))
        raise OSError("source read failed")

    monkeypatch.setattr(local_files.shutil, "copyfileobj", fail)
    with pytest.raises(OSError, match="source read failed"):
        local_files.atomic_copy(source, target)
    assert not target.exists()
    assert not list(tmp_path.glob(".app-storage-*"))


def test_failed_stream_preserves_destination(tmp_path):
    target = tmp_path / "existing"
    target.write_bytes(b"old")

    def chunks():
        yield b"partial"
        raise OSError("input stream failed")

    with pytest.raises(OSError, match="input stream failed"):
        local_files.atomic_write_stream(target, chunks())
    assert target.read_bytes() == b"old"
    assert list(tmp_path.iterdir()) == [target]


def test_stream_is_published_only_after_complete_iteration(tmp_path):
    target = tmp_path / "existing"
    target.write_bytes(b"old")

    def chunks():
        for _ in range(3):
            assert target.read_bytes() == b"old"
            yield b"new"

    local_files.atomic_write_stream(target, chunks())
    assert target.read_bytes() == b"newnewnew"
    local_files.atomic_write_stream(target, [])
    assert target.read_bytes() == b""
