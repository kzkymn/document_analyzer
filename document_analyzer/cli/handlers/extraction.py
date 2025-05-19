"""
条件とファクトの抽出/読み込み処理を提供するモジュール
"""

from pathlib import Path

from rich.console import Console

from ...core.pair_check import PairCheckItemType

console = Console()


from pathlib import Path
from typing import List, Optional, Union

from rich.console import Console

from ...core.extractor import TextExtractor  # TextExtractorの型ヒントのためにインポート
from ...core.pair_check import PairCheckItem, PairCheckItemType

console = Console()


def extract_or_load_items(
    extractor: TextExtractor,
    item_type: str,  # 'conditions' or 'facts'
    file_path: Union[str, Path],
    output_path: Union[str, Path],
    should_extract: bool,  # 抽出するかどうかを明示的に指定
    source_context: Optional[
        str
    ] = None,  # ターゲット抽出時に使用するソースのコンテキスト
) -> List[PairCheckItem]:
    """
    条件またはファクトを抽出または読み込む

    Args:
        extractor: TextExtractorインスタンス
        item_type: 'conditions'または'facts'
        file_path: ソースファイルまたはターゲットファイルのパス
        output_path: 出力先ファイルのパス
        should_extract: 抽出が必要な場合はTrue、既存ファイルを読み込む場合はFalse
        source_context: ターゲットファイルの場合、ソースファイルの内容または抽出された条件

    Returns:
        抽出または読み込まれた項目のリスト
    """
    items: List[PairCheckItem] = []
    item_type_obj = (
        PairCheckItemType.CONDITION
        if item_type == "conditions"
        else PairCheckItemType.FACT
    )
    item_name = "チェック条件" if item_type == "conditions" else "ファクト"
    output_path_obj = Path(output_path)

    if should_extract:
        # 項目を抽出
        console.print(f"[bold blue]{item_name}を抽出中...[/bold blue]")
        file_content = Path(file_path).read_text(encoding="utf-8")

        if item_type == "conditions":
            items = extractor.extract_conditions(file_content, str(file_path))
        else:  # item_type == "facts"
            items = extractor.extract_facts(
                file_content,
                str(file_path),
            )

        # 抽出結果をファイルに保存
        extractor.file_handler.save_items_to_file(items, output_path_obj)
        console.print(
            f"[bold green]{len(items)}個の{item_name}を抽出しました。保存先: {output_path}[/bold green]"
        )
        # 抽出結果を編集した場合、次回実行時に既存ファイルを使用するには '--use-existing-{item_type}' オプションを指定してください。
        console.print(
            f"[yellow]{item_name}ファイルを編集した場合、次回実行時に既存ファイルを使用するには '--use-existing-{item_type}' オプションを指定してください。[/yellow]"
        )
    else:
        # 既存のファイルを読み込み
        console.print(
            f"[bold blue]既存の{item_name}ファイルを読み込み中: {output_path}[/bold blue]"
        )
        if output_path_obj.exists():
            items = extractor.load_items_from_file(output_path_obj, item_type_obj)
            console.print(
                f"[bold green]{len(items)}個の{item_name}を読み込みました: {output_path}[/bold green]"
            )
        else:
            console.print(
                f"[bold blue]指定された{item_name}ファイルが見つかりません: {output_path}[/bold blue]"
            )
            # ファイルが見つからない場合は空のリストを返す

    return items
