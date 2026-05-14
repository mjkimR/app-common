import os.path
import sys
from contextvars import ContextVar

from loguru import logger

from app_base.config import get_app_settings

# Request ID context variable
request_id_var = ContextVar[str]("request_id", default="N/A")


def get_request_id():
    """Get the current request ID from context"""
    return request_id_var.get()


def set_request_id(req_id: str):
    """Set the request ID in context"""
    request_id_var.set(req_id)


def global_patcher(record):
    """Global patch function to inject dynamic data into the log record's 'extra' dict"""
    request_id = get_request_id()
    if request_id:
        record["extra"]["request_id"] = request_id.ljust(8)
    else:
        record["extra"]["request_id"] = "N/A".ljust(8)

    # Universal extension point for dynamic prefix and suffix
    if "custom_prefix" not in record["extra"]:
        record["extra"]["custom_prefix"] = ""
    if "custom_suffix" not in record["extra"]:
        record["extra"]["custom_suffix"] = ""


def setup_logger():
    """Setup the logger with console and file handlers"""
    # Remove default handler
    logger.remove()

    # Log settings (App settings)
    settings = get_app_settings()
    log_file_path = os.path.join(settings.LOG_PATH)
    common_file_config = {
        "sink": log_file_path,
        "level": settings.LOG_LEVEL,
        "rotation": "1 day",
        "retention": "30 days",
        "compression": "zip",
        "diagnose": False,
    }

    # Apply the patch globally to the core logger object
    logger.configure(patcher=global_patcher)

    if settings.LOG_JSON_FORMAT:
        # 1. Console (JSON)
        logger.add(
            sys.stdout,
            level=settings.LOG_LEVEL,
            serialize=True,
            backtrace=True,
            diagnose=False,
        )
        # 2. File (JSON)
        logger.add(
            **common_file_config,
            serialize=True,
            backtrace=True,
        )
    else:
        # 1. Console (Text + Color)
        logger.add(
            sys.stdout,
            format=(
                "[<yellow>{extra[request_id]}</yellow>] "
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "{extra[custom_prefix]}<level>{message}</level>{extra[custom_suffix]} "
                "<cyan>({name}:{line})</cyan>"
            ),
            level=settings.LOG_LEVEL,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )
        # 2. File (Text)
        logger.add(
            **common_file_config,
            format=(
                "[{extra[request_id]}] "
                "{time:YYYY-MM-DD HH:mm:ss} | "
                "{level: <8} | "
                "{extra[custom_prefix]}{message}{extra[custom_suffix]} "
                "({name}:{line})"
            ),
            backtrace=True,
        )
    return logger


setup_logger()
