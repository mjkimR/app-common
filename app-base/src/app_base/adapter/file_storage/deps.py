from fastapi import Request

from app_base.adapter.file_storage.interface import FileStorageClient


def get_file_storage_provider(request: Request) -> FileStorageClient:
    """
    Returns the file storage client instance.
    The return type may vary depending on KIND.
    """
    return request.app.state.file_storage
