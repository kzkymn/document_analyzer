"""
コマンドラインインターフェースパッケージ
"""

import click

from document_analyzer.cli.commands.check import check_command


@click.group(invoke_without_command=True)
@click.version_option()
@click.pass_context
def cli(ctx):
    """文書分析ツール"""
    if ctx.invoked_subcommand is None:
        ctx.invoke(check_command)


# コマンドを登録
cli.add_command(check_command, name="check")


def main():
    """エントリーポイント"""
    cli()
