from typing import Any


class NoSQLDBException(Exception):
    """Base exception for all NoSQL DB operations."""

    message: str = "NoSQL DB error occurred"

    def __init__(self, message: str | None = None, **kwargs: Any) -> None:
        if message:
            self.message = message
        super().__init__(self.message)


class NotFoundException(NoSQLDBException):
    """Exception raised when a document is not found."""

    message: str = "Document not found"
