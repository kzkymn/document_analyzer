"""
ペアチェック処理を提供するモジュール
"""

import json
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown

console = Console()


def run_pair_check(analyzer, conditions, facts, source_file, target_file, output=None):
    """
    ペアチェックを実行する

    Args:
        analyzer: TextComparisonAnalyzerインスタンス
        conditions: 条件のリスト
        facts: ファクトのリスト
        source_file: ソースファイルのパス
        target_file: ターゲットファイルのパス
        output: 出力先ファイルのパス

    Returns:
        ペアチェック結果
    """
    console.print("[bold blue]ペアチェックを実行します...[/bold blue]")

    # ペアチェッカーを初期化してチェックを実行
    from ...core.pair_checker import PairChecker

    checker = PairChecker(analyzer.processor)
    result = checker.check_pairs(conditions, facts)

    # ペアチェックの結果をJSONファイルとして保存
    pair_check_output = "pair_check_output.json"
    console.print(
        f"[bold blue]ペアチェック結果をファイルに保存します: {pair_check_output}[/bold blue]"
    )

    try:
        with open(pair_check_output, "w", encoding="utf-8") as f:
            json.dump(result.dict(), f, ensure_ascii=False, indent=2)
        console.print(
            f"[bold green]ペアチェックの結果を保存しました: {pair_check_output}[/bold green]"
        )
    except AttributeError as e:
        console.print(
            f"[bold red]エラー: ペアチェックの結果を保存できませんでした。属性エラー: {e}[/bold red]"
        )

    # レポートを生成（指定されている場合）
    if output:
        report = analyzer.report_generator.generate_pair_check_report(
            result, source_file, target_file
        )
        analyzer.report_generator.save_report(report, output)
        console.print(f"レポートを保存しました: {output}")
    else:
        # レポートを生成して標準出力に表示
        report = analyzer.report_generator.generate_pair_check_report(
            result, source_file, target_file
        )
        console.print(Markdown(report))

    return result
