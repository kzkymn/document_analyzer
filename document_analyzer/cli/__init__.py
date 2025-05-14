"""
コマンドラインインターフェースパッケージ
"""

import click

from .commands.check import check_command
from .commands.serve import serve_command


@click.group()
@click.version_option()
def cli():
    """文書分析ツール"""
    pass


# コマンドを登録
cli.add_command(check_command, name="check")
cli.add_command(serve_command, name="serve")


def main():
    """エントリーポイント"""
    cli()
