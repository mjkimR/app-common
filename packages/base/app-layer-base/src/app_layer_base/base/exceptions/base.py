from __future__ import annotations

from collections.abc import Sequence
from http import HTTPStatus
from typing import Any

from devkit.advisory import Actor, Advisory, AdvisoryError, ExitCode, Level, Retry

__all__ = [
    "Actor",
    "Advisory",
    "AdvisoryError",
    "CustomException",
    "ExitCode",
    "Level",
    "Retry",
]


class CustomException(AdvisoryError):
    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    title: str = "Internal Server Error"
    message: str = "Internal Server Error"
    log_message: str | None = None
    trace: bool = True
    code: str = "INTERNAL_SERVER_ERROR"

    def __init__(
        self,
        message: str | None = None,
        log_message: str | None = None,
        status_code: int | None = None,
        title: str | None = None,
        trace: bool | None = None,
        *,
        code: str | None = None,
        actor: Actor | None = None,
        retry: Retry | None = None,
        guardrail: bool | None = None,
        input_error: bool | None = None,
        retry_after: str | None = None,
        fix: str | None = None,
        what_to_report: str | None = None,
        target_files: Sequence[str] | None = None,
        details: Sequence[str] | None = None,
        exit_code: ExitCode | None = None,
    ) -> None:
        resolved_message = message if message is not None else self.message
        super().__init__(
            resolved_message,
            *(details or ()),
            code=code,
            actor=actor,
            retry=retry,
            guardrail=guardrail,
            input_error=input_error,
            retry_after=retry_after,
            fix=fix,
            what_to_report=what_to_report,
            target_files=target_files,
            exit_code=exit_code,
        )
        if log_message is not None:
            self.log_message = log_message
        if status_code is not None:
            self.status_code = status_code
        if title is not None:
            self.title = title
        if trace is not None:
            self.trace = trace

        if log_message is None:
            self.log_message = self.message

    def to_dict(self, *, include_advisory: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "title": self.title,
            "message": self.message,
            "log_message": self.log_message,
            "status_code": self.status_code,
            "code": self.code,
        }
        if include_advisory:
            data["advisory"] = self.advisory.to_dict()
        return data
