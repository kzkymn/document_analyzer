"""
コマンドラインインターフェースパッケージ
"""

import click

from document_analyzer.cli.commands.check import check_command


@click.group()
@click.version_option()
def cli():
    """文書分析ツール"""
    pass


# コマンドを登録
cli.add_command(check_command, name="check")


def main():
    """エントリーポイント"""
    cli()
