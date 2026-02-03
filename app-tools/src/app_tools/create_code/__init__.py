import click

from app_tools.create_module.create_feature import create_feature
from app_tools.utils.config import get_app_home_dir


@click.group()
def create_code():
    """Create code"""
    pass


@create_code.command()
@click.option("--name", prompt="Feature name", help="The name of the feature in CamelCase.")
@click.option("--plural", help="The plural name of the feature in snake_case. Optional.")
def feature(name: str, plural: str | None):
    """Create a new feature module"""
    base_dir = get_app_home_dir()
    create_feature(name=name, plural=plural, base_dir=base_dir)
