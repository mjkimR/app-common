import functools

import click


def handle_cli_errors(func):
    """Convert ValueError and RuntimeError into ClickException so they print without a traceback."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (ValueError, RuntimeError) as e:
            raise click.ClickException(str(e)) from e

    return wrapper
