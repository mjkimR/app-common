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
    "app_base/core/middlewares",
]


def _is_whitelisted(filename: str, whitelist: list[str]) -> bool:
    sep = os.sep

    for pkg in whitelist:
        dir_pattern = f"{sep}{pkg}{sep}"
        file_pattern = f"{sep}{pkg}.py"
        if dir_pattern in filename or filename.endswith(file_pattern):
            return True
    return False


def get_exception_traceback_str(exc: Exception) -> str:
    """
    Returns a filtered or full traceback string depending on LOG_SIMPLE_TRACEBACK setting.
    """
    # If the setting is off (False) -> return the original full stack
    settings = get_app_settings()

    if not settings.LOG_SIMPLE_TRACEBACK:
        # Return the full stack + error message, same as Python default behavior
        return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    tb_list = traceback.extract_tb(exc.__traceback__)

    filtered_frames = []
    total_frames = len(tb_list)

    for i, frame in enumerate(tb_list):
        filename = frame.filename

        # 1. Check if this is the last frame (error point)
        # If it is the last frame, always show it regardless of package
        is_last_frame = i == total_frames - 1

        if is_last_frame:
            filtered_frames.append(frame)
            continue

        # 2. Check for noise patterns (hide middleware calls in the middle)
        normalized_path = filename.replace(os.sep, "/")
        if any(pattern in normalized_path for pattern in TRACEBACK_NOISE_PATTERNS):
            continue

        # 3. Whitelist logic (filtering site-packages)
        is_external_lib = "site-packages" in filename or "dist-packages" in filename
        if is_external_lib:
            if _is_whitelisted(filename, settings.LOG_TRACEBACK_WHITELIST):
                filtered_frames.append(frame)
        else:
            # Project code or standard library
            filtered_frames.append(frame)

    # Formatting
    stack_str = "".join(traceback.format_list(filtered_frames))
    exc_msg = "".join(traceback.format_exception_only(type(exc), exc))

    return f"Traceback (Filtered):\n{stack_str}{exc_msg}"
