from pathlib import Path

import click
from app_error import AppError

from app_tools.create_code.create_feature import create_feature
from app_tools.create_code.create_web_feature import create_web_feature


@click.group()
def create_code():
    """Create code"""
    pass


@create_code.command()
@click.option("--name", prompt="Feature name", help="The name of the feature in CamelCase.")
@click.option("--plural", help="The plural name of the feature in snake_case. Optional.")
@click.option(
    "--prefix", help="The prefix path for the feature directory (e.g., 'app/features'). Defaults to 'app/features'."
)
def feature(name: str, plural: str | None, prefix: str | None):
    """Create a new backend feature module"""
    base_dir = Path.cwd()
    try:
        create_feature(name=name, plural=plural, base_dir=base_dir, feature_prefix=prefix)
    except AppError as e:
        raise click.ClickException("\n".join(e.lines())) from e


@create_code.command("web-feature")
@click.option("--name", prompt="Web feature name", help="The name of the feature in CamelCase (e.g., Project).")
@click.option("--plural", help="The plural name of the feature in snake_case. Optional.")
@click.option("--prefix", help="The prefix path for the web feature directory (e.g., 'src/lib/features').")
def web_feature(name: str, plural: str | None, prefix: str | None):
    """Create a new Svelte 5 web feature module"""
    base_dir = Path.cwd()
    try:
        create_web_feature(name=name, plural=plural, base_dir=base_dir, feature_prefix=prefix)
    except AppError as e:
        raise click.ClickException("\n".join(e.lines())) from e
