import click

from app_tools.create_module import create_code


@click.group()
def cli():
    """App Tools CLI"""
    pass


cli.add_command(create_code)


if __name__ == "__main__":
    cli()
