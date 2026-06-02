from pathlib import Path

import click

from app_tools.create_code.create_feature import create_feature


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
    """Create a new feature module"""
    base_dir = Path.cwd()
    create_feature(name=name, plural=plural, base_dir=base_dir, feature_prefix=prefix)
