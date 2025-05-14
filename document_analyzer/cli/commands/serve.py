"""
serveコマンドの実装
"""

import sys

import click
from rich.console import Console

from ...utils.logging import logger

console = Console()


@click.command()
@click.option("--host", default="127.0.0.1", help="ホストアドレス")
@click.option("--port", "-p", default=8000, type=int, help="ポート番号")
@click.option("--reload", is_flag=True, help="ファイル変更時に自動リロード")
def serve_command(host: str, port: int, reload: bool):
    """
    APIサーバーを起動する。

    FastAPIベースのREST APIサーバーを起動し、
    文書分析のAPIエンドポイントを提供する。
    """
    try:
        import uvicorn

        from ...api import app

        console.print(f"APIサーバーを起動します: http://{host}:{port}")
        uvicorn.run("document_analyzer.api:app", host=host, port=port, reload=reload)

    except ImportError:
        console.print(
            "[bold red]エラー:[/bold red] FastAPIとuvicornがインストールされていません。"
        )
        console.print("pip install fastapi uvicorn を実行してください。")
        sys.exit(-1)

    except Exception as e:
        logger.error(f"サーバー起動中にエラーが発生しました: {str(e)}")
        console.print(f"[bold red]エラー:[/bold red] {str(e)}")
        sys.exit(-1)
