import click

from app_tools.commands.check_arch import check_arch
from app_tools.commands.dev import dev
from app_tools.commands.doctor import doctor
from app_tools.commands.get_env_spec import get_env_spec
from app_tools.commands.guide import guide
from app_tools.commands.run import run
from app_tools.commands.update import update
from app_tools.create_code import create_code


@click.group()
def cli():
    """App Tools CLI"""
    pass


cli.add_command(create_code)
cli.add_command(get_env_spec)
cli.add_command(dev)
cli.add_command(doctor)
cli.add_command(guide)
cli.add_command(update)
cli.add_command(check_arch)
cli.add_command(run)

if __name__ == "__main__":
    cli()
