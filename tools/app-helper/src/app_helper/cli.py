import click

from app_helper.diff import copy_diff
from app_helper.prompts import prompt


@click.group()
def cli():
    """App Helper CLI - General-purpose developer tools and utilities"""
    pass


# Register command groups
cli.add_command(prompt)
cli.add_command(copy_diff)

if __name__ == "__main__":
    cli()
