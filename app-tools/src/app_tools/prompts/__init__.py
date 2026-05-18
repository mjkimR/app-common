import functools

import click

from app_tools.prompts.git_diff import build_prompt, build_review_prompt, copy_to_clipboard


def _handle_prompt_errors(func):
    """Common error handling decorator: converts ValueError and RuntimeError to ClickException."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (ValueError, RuntimeError) as e:
            raise click.ClickException(str(e)) from e

    return wrapper


@click.group()
def prompt():
    """Generate prompt"""
    pass


@prompt.command()
@click.option(
    "--language",
    "-l",
    default="English",
    show_default=True,
    help="Language for the commit message (e.g. English, Korean, Japanese).",
)
@_handle_prompt_errors
def commit(language: str):
    """Generate a commit message prompt from staged git changes and copy to clipboard."""
    prompt_text = build_prompt(language=language)
    copy_to_clipboard(prompt_text)
    click.echo(f"✅ Prompt copied to clipboard! (language: {language})")


@prompt.command()
@click.option(
    "--language",
    "-l",
    default="Korean",
    show_default=True,
    help="Language for the code review (e.g. English, Korean, Japanese).",
)
@click.option(
    "--staged",
    "-s",
    is_flag=True,
    default=False,
    help="Use only staged changes (--cached). Defaults to HEAD diff.",
)
@_handle_prompt_errors
def review(language: str, staged: bool):
    """Generate a code review prompt from git changes and copy to clipboard."""
    prompt_text = build_review_prompt(language=language, staged_only=staged)
    copy_to_clipboard(prompt_text)
    click.echo(f"✅ Code review prompt copied to clipboard! (language: {language}, staged: {staged})")
