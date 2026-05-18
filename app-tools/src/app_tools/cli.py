import click

from app_tools.commands.get_env_spec import get_env_spec
from app_tools.create_code import create_code
from app_tools.prompts import prompt


@click.group()
def cli():
    """App Tools CLI"""
    pass


cli.add_command(create_code)
cli.add_command(get_env_spec)
cli.add_command(prompt)

if __name__ == "__main__":
    cli()
