import itertools
import os
import traceback

from app_base.config import get_app_settings

TRACEBACK_NOISE_PATTERNS = [
    "starlette/middleware",
    "starlette/routing",
    "fastapi/middleware",
    "uvicorn/protocols",
    "uvicorn/lifespan",
    "anyio/",
    "asyncio/tasks",
    "contextlib/",
    "app_base/core/middlewares",
    "app_base/base",
]


def _is_whitelisted(filename: str, whitelist: list[str]) -> bool:
    sep = os.sep

    for pkg in whitelist:
        dir_pattern = f"{sep}{pkg}{sep}"
        file_pattern = f"{sep}{pkg}.py"
        if dir_pattern in filename or filename.endswith(file_pattern):
            return True
    return False


def _get_chaining_message(previous: BaseException, current: BaseException) -> str | None:
    if getattr(previous, "__cause__", None) is current:
        return "\nThe above exception was the direct cause of the following exception:\n\n"

    if getattr(previous, "__context__", None) is current:
        return "\nDuring handling of the above exception, another exception occurred:\n\n"

    return None


def get_exception_traceback_str(exc: Exception) -> str:
    """
    Returns a filtered or full traceback string depending on LOG_SIMPLE_TRACEBACK setting.
    Includes chained exceptions (raise ... from ...) while preventing cyclic references.
    """
    settings = get_app_settings()

    # If the setting is off (False) -> return the original full stack
    if not settings.LOG_SIMPLE_TRACEBACK:
        return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    def _format_single_exception(e: BaseException) -> str:
        """Formats and applies filtering for a single exception object."""
        tb_list = traceback.extract_tb(e.__traceback__)
        filtered_frames = []
        total_frames = len(tb_list)

        for i, frame in enumerate(tb_list):
            filename = frame.filename

            # 1. Always include the last frame (the exact error point)
            is_last_frame = i == total_frames - 1

            if is_last_frame:
                filtered_frames.append(frame)
                continue

            # 2. Skip noise patterns (hide middleware calls in the middle)
            normalized_path = filename.replace(os.sep, "/")
            if any(pattern in normalized_path for pattern in TRACEBACK_NOISE_PATTERNS):
                continue

            # 3. Whitelist logic (filter site-packages, keep whitelisted ones)
            is_external_lib = "site-packages" in filename or "dist-packages" in filename
            if is_external_lib and not _is_whitelisted(filename, settings.LOG_TRACEBACK_WHITELIST):
                continue

            # Project code, standard library, or whitelisted external library
            filtered_frames.append(frame)

        # Format filtered frames into a string
        stack_str = "".join(traceback.format_list(filtered_frames))
        exc_msg = "".join(traceback.format_exception_only(type(e), e))

        return f"{stack_str}{exc_msg}"

    # 1. Collect the exception chain (cause/context) safely to prevent infinite loops
    exceptions = []
    seen_ids = set()
    curr = exc

    while curr is not None and id(curr) not in seen_ids:
        seen_ids.add(id(curr))
        exceptions.append(curr)

        # Explicit chain (raise ... from ...)
        if getattr(curr, "__cause__", None) is not None:
            curr = curr.__cause__
        # Implicit chain (context)
        elif getattr(curr, "__context__", None) is not None and not getattr(curr, "__suppress_context__", False):
            curr = curr.__context__
        else:
            curr = None

    # 2. Assemble formatted blocks in reverse order (root cause first, latest exception last)
    blocks = ["Traceback (Filtered):\n"]
    ordered_exceptions = list(reversed(exceptions))
    for e, next_e in itertools.pairwise(ordered_exceptions):
        blocks.append(_format_single_exception(e))

        # Add chaining messages between exceptions (mirrors standard Python behavior)
        message = _get_chaining_message(next_e, e)
        if message is not None:
            blocks.append(message)

    if ordered_exceptions:
        blocks.append(_format_single_exception(ordered_exceptions[-1]))

    return "".join(blocks)
