"""
設定ファイル関連の処理を提供するモジュール
"""

from pathlib import Path

from rich.console import Console

from ...utils.config import Config, config

console = Console()


def load_config(config_path):
    """
    設定ファイルを読み込む

    Args:
        config_path: 設定ファイルのパス

    Returns:
        (成功したかどうか, エラーメッセージ)
    """
    # 設定ファイルの存在を確認
    config_file_path = Path(config_path)
    if not config_file_path.exists():
        console.print(
            f"[bold red]エラー:[/bold red] 設定ファイルが見つかりません: {config_file_path.absolute()}"
        )
        console.print("\n以下を確認してください：")
        console.print("1. 指定したパスが正しいか")
        console.print("2. ファイルが実際に存在するか")
        console.print("3. ファイルの読み取り権限があるか")
        console.print("\n例：")
        console.print(
            "  document-analyzer check -s source.txt -t target.txt -c sample_input/weekly_report_check/config.yaml"
        )

        # サンプル設定ファイルの場所を提案
        sample_configs = ["sample_input/weekly_report_check/config.yaml"]

        for sample in sample_configs:
            if Path(sample).exists():
                console.print(
                    f"\n[green]利用可能なサンプル設定ファイル:[/green] {sample}"
                )
                console.print(
                    f"  document-analyzer check -s source.txt -t target.txt -c {sample}"
                )

        return False, "設定ファイルが見つかりません"

    # 設定ファイルを読み込み、グローバルなconfigインスタンスを更新する
    try:
        # 新しい設定を読み込む
        new_config = Config(config_path)

        # グローバルなconfigインスタンスの設定を更新する
        config.config = new_config.config
        config.config_path = new_config.config_path

        return True, None
    except Exception as e:
        console.print(
            f"[bold red]エラー:[/bold red] 設定ファイルの読み込みに失敗しました: {str(e)}"
        )
        console.print("\n設定ファイルの形式が正しいか確認してください。")
        console.print("YAMLファイルの例：")
        console.print(
            """
# プロンプト設定
prompt:
  template_path: "prompt.txt"  # プロンプトテンプレートのパス（相対パスまたは絶対パス）
  description: "週次レポートチェック"  # 説明（オプション）
"""
        )
        return False, f"設定ファイルの読み込みに失敗しました: {str(e)}"
