import functools

import click
from app_error import AppError


def handle_cli_errors(func):
    """Convert AppError, ValueError, and RuntimeError into ClickException with structured output without a traceback."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AppError as e:
            lines = e.lines()
            raise click.ClickException("\n".join(lines)) from e
        except (ValueError, RuntimeError) as e:
            raise click.ClickException(str(e)) from e

    return wrapper
