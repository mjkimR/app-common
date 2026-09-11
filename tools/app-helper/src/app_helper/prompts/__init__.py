import click

from app_helper.clipboard import copy_text
from app_helper.errors import handle_cli_errors
from app_helper.prompts.git_diff import build_prompt, build_review_prompt


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
@handle_cli_errors
def commit(language: str):
    """Generate a commit message prompt from staged git changes and copy to clipboard."""
    prompt_text = build_prompt(language=language)
    copy_text(prompt_text)
    click.echo(f"✅ Prompt copied to clipboard! (language: {language})")


@prompt.command()
@click.option(
    "--language",
    "-l",
    default="English",
    show_default=True,
    help="Language for the code review (e.g. English, Korean, Japanese).",
)
@click.option(
    "--head/--no-head",
    is_flag=True,
    default=False,
    help="Use HEAD diff (staged + unstaged changes). Defaults to staged diff.",
)
@click.option(
    "--last/--no-last",
    is_flag=True,
    default=False,
    help="Review the last commit (HEAD~1..HEAD).",
)
@handle_cli_errors
def review(language: str, head: bool, last: bool):
    """Generate a code review prompt from git changes and copy to clipboard."""
    prompt_text = build_review_prompt(language=language, head_only=head, last_commit=last)
    copy_text(prompt_text)

    target = "last commit" if last else "HEAD" if head else "staged"
    click.echo(f"✅ Code review prompt copied to clipboard! (language: {language}, target: {target})")
