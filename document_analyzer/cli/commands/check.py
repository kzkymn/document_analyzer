"""
checkコマンドの実装
"""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.markdown import Markdown

from ...core.analyzer import TextComparisonAnalyzer
from ...core.pair_check import PairCheckItem, PairCheckItemType
from ...core.processor import ComplianceStatus
from ...utils.encoding import read_text_auto
from ...utils.logging import logger
from ..handlers.config import load_config
from ..handlers.extraction import extract_or_load_items
from ..handlers.pair_check import run_pair_check

console = Console()


class CheckCommand:
    """
    checkコマンドの処理をカプセル化するクラス
    """

    def __init__(
        self,
        config_path: str,
        source_file: str,
        target_file: str,
        output: Optional[str] = None,
        llm: Optional[str] = None,
        verbose: bool = False,
        extract_only: Optional[str] = None,
        use_existing_conditions: bool = False,
        use_existing_facts: bool = False,
        conditions_output: str = "conditions_output.json",
        facts_output: str = "facts_output.json",
        yes: bool = False,
        skip_condition_extraction: bool = False,
        skip_fact_extraction: bool = False,
    ):
        self.config_path = config_path
        self.source_file = source_file
        self.target_file = target_file
        self.output = output
        self.llm = llm
        self.verbose = verbose
        self.extract_only = extract_only
        self.use_existing_conditions = use_existing_conditions
        self.use_existing_facts = use_existing_facts
        self.conditions_output = conditions_output
        self.facts_output = facts_output
        self.yes = yes
        self.skip_condition_extraction = skip_condition_extraction
        self.skip_fact_extraction = skip_fact_extraction
        self.console = Console(force_terminal=True)
        self.analyzer = None

    def validate_options(self) -> bool:
        """
        checkコマンドのオプションを検証する
        """
        return True

    def load_configuration(self) -> bool:
        """
        設定ファイルを読み込む
        """
        success, error_message = load_config(self.config_path)
        if not success:
            self.console.print(f"[bold red]エラー:[/bold red] {error_message}")
            return False
        return True

    def initialize_analyzer(self):
        """
        分析器を初期化する
        """
        self.analyzer = TextComparisonAnalyzer(llm_name=self.llm)

    def run(self):
        """
        checkコマンドの実行ロジック
        """
        try:
            if not self.validate_options():
                sys.exit(1)

            if not self.load_configuration():
                sys.exit(1)

            self.initialize_analyzer()

            from ...core.extractor import TextExtractor

            extractor = TextExtractor(self.analyzer.processor)

            conditions = []
            facts = []
            source_content = None
            target_content = None

            # --extract-only オプションの処理
            if self.extract_only:
                if self.extract_only in ["conditions", "both"]:
                    conditions = extract_or_load_items(
                        extractor,
                        "conditions",
                        self.source_file,
                        self.conditions_output,
                        True,  # should_extract
                    )
                    self.console.print(
                        f"[bold green]条件の抽出が完了しました。[/bold green]"
                    )
                if self.extract_only in ["facts", "both"]:
                    # ターゲット抽出時はソースファイル内容または条件を渡す
                    source_context = None
                    if self.extract_only == "both" and conditions:
                        source_context = conditions  # conditionsをそのまま渡す
                    elif self.extract_only == "both":
                        # このケースは、conditionsが空の場合なので、source_contextは不要
                        # または、必要であればread_text_auto(self.source_file)を渡す
                        # ただし、extract_factsはList[PairCheckItem]を期待するので、
                        # ここで文字列を渡すのは適切ではない。
                        # 現状のロジックでは、extract_only="both"の場合、conditionsは必ず抽出されるため、
                        # このelifブロックは実質的に到達しない。
                        pass

                    facts = extract_or_load_items(
                        extractor,
                        "facts",
                        self.target_file,
                        self.facts_output,
                        should_extract=True,
                        context_items=source_context,
                    )
                    self.console.print(
                        f"[bold green]ファクトの抽出が完了しました。[/bold green]"
                    )
                sys.exit(0)

            # 通常の分析フロー (条件とファクトの抽出)
            # ソースファイルの処理 (条件)
            if self.skip_condition_extraction:
                self.console.print(
                    "[bold blue]--skip-condition-extraction オプションが指定されました。条件の抽出をスキップします。[/bold blue]"
                )
                conditions = []
            elif self.use_existing_conditions:
                self.console.print(
                    "[bold blue]既存の条件ファイルを読み込みます。[/bold blue]"
                )
                # オプションが指定されている場合のみ既存ファイルを読み込む
                if Path(self.conditions_output).exists():
                    conditions = extractor.file_handler.load_items_from_file(
                        self.conditions_output, PairCheckItemType.CONDITION
                    )
                else:
                    self.console.print(
                        f"[bold yellow]警告: 指定された条件ファイルが見つかりません: {self.conditions_output}[/bold yellow]"
                    )
            else:
                self.console.print(
                    f"[bold blue]ソースファイル ({self.source_file}) の抽出要否を判断します。[/bold blue]"
                )
                source_content = read_text_auto(self.source_file)
                file_size = Path(self.source_file).stat().st_size
                file_head = source_content[:1000]  # 冒頭1000文字を使用

                need_extract_conditions, reason = (
                    self.analyzer.processor.should_extract_items(
                        self.source_file, file_size, file_head
                    )
                )
                # LLMの判断結果と根拠をコンソールに表示
                self.console.print(
                    f"[bold yellow]LLMの判断:[/bold yellow] ソースファイルから条件を抽出{'する' if need_extract_conditions else 'しない'}"
                )
                self.console.print(f"[bold yellow]判断根拠:[/bold yellow] {reason}")

                if need_extract_conditions:
                    conditions = extract_or_load_items(
                        extractor,
                        "conditions",
                        self.source_file,
                        self.conditions_output,
                        True,  # should_extract
                    )
                else:
                    conditions = []
                    self.console.print(
                        "[bold blue]条件の抽出は不要と判断されました。[/bold blue]"
                    )

            # ターゲットファイルの処理 (ファクト)
            if self.skip_fact_extraction:
                self.console.print(
                    "[bold blue]--skip-fact-extraction オプションが指定されました。ファクトの抽出をスキップします。[/bold blue]"
                )
                facts = []
            elif self.use_existing_facts:
                self.console.print(
                    "[bold blue]既存のファクトファイルを読み込みます。[/bold blue]"
                )
                # オプションが指定されている場合のみ既存ファイルを読み込む
                if Path(self.facts_output).exists():
                    facts = extractor.file_handler.load_items_from_file(
                        self.facts_output, PairCheckItemType.FACT
                    )
                else:
                    self.console.print(
                        f"[bold yellow]警告: 指定されたファクトファイルが見つかりません: {self.facts_output}[/bold yellow]"
                    )
            else:
                self.console.print(
                    f"[bold blue]ターゲットファイル ({self.target_file}) の抽出要否を判断します。[/bold blue]"
                )
                target_content = read_text_auto(self.target_file)
                file_size = Path(self.target_file).stat().st_size
                file_head = target_content[:1000]  # 冒頭1000文字を使用

                # ターゲット抽出判断時はソースファイル内容または条件を渡す
                source_context = None
                if conditions:
                    source_context = "\n".join([c.text for c in conditions])
                elif source_content:
                    source_context = source_content

                need_extract_facts, reason = (
                    self.analyzer.processor.should_extract_items(
                        self.target_file,
                        file_size,
                        file_head,
                        source_context=source_context,
                    )
                )
                # LLMの判断結果と根拠をコンソールに表示
                self.console.print(
                    f"[bold yellow]LLMの判断:[/bold yellow] ターゲットファイルからファクトを抽出{'する' if need_extract_facts else 'しない'}"
                )
                self.console.print(f"[bold yellow]判断根拠:[/bold yellow] {reason}")

                if need_extract_facts:
                    facts = extract_or_load_items(
                        extractor,
                        "facts",
                        self.target_file,
                        self.facts_output,
                        True,  # should_extract
                        source_context=source_context,
                    )
                else:
                    facts = []
                    self.console.print(
                        "[bold blue]ファクトの抽出は不要と判断されました。[/bold blue]"
                    )

            # 抽出結果の確認プロンプト
            if not self.yes:
                self.console.print(
                    "\n[bold yellow]抽出された条件とファクトを確認してください。[/bold yellow]"
                )
                if len(conditions) == 0:
                    self.console.print(f"条件: {self.conditions_output} (抽出不要)")
                else:
                    self.console.print(
                        f"条件: {self.conditions_output} ({len(conditions)}個)"
                    )
                if len(facts) == 0:
                    self.console.print(f"ファクト: {self.facts_output} (抽出不要)")
                else:
                    self.console.print(
                        f"ファクト: {self.facts_output} ({len(facts)}個)"
                    )

                self.console.print(
                    "[bold yellow]確認ログ: 条件とファクトの抽出結果を確認しています。[/bold yellow]"
                )
                if not click.confirm("この抽出結果で分析を実行しますか？"):
                    self.console.print(
                        "[bold red]分析を中止しました。ユーザーが確認を拒否しました。[/bold red]"
                    )
                    logger.info(
                        "ユーザーが抽出結果の確認を拒否しました。条件数: %d, ファクト数: %d, ソースファイル: %s, ターゲットファイル: %s",
                        len(conditions),
                        len(facts),
                        self.source_file,
                        self.target_file,
                    )
                    sys.exit(0)

                # 確認後にファイルが編集されている可能性を考慮し、再度読み込みは行わない
                # ここでの再読み込み処理は削除

            # 分析処理の決定と実行
            if conditions and facts:
                self.console.print(
                    "[bold blue]フルペアチェックを実行します。[/bold blue]"
                )
                result = run_pair_check(
                    self.analyzer,
                    conditions,
                    facts,
                    self.source_file,
                    self.target_file,
                    self.output,
                )
            elif conditions:
                self.console.print(
                    "[bold blue]条件とターゲット全文を比較します。[/bold blue]"
                )
                # ターゲットファイルの全テキストをファクトとして使用
                if target_content is None:  # まだ読み込んでいない場合
                    target_content = read_text_auto(self.target_file)
                facts = [
                    PairCheckItem(
                        text=target_content,
                        source=str(self.target_file),
                        item_type=PairCheckItemType.FACT,
                        id=1,
                    )
                ]
                result = run_pair_check(
                    self.analyzer,
                    conditions,
                    facts,
                    self.source_file,
                    self.target_file,
                    self.output,
                )
            elif facts:
                self.console.print(
                    "[bold blue]ファクトとソース全文を比較します。[/bold blue]"
                )
                # ソースファイルの全テキストを条件として使用
                if source_content is None:  # まだ読み込んでいない場合
                    source_content = read_text_auto(self.source_file)
                conditions = [
                    PairCheckItem(
                        text=source_content,
                        source=str(self.source_file),
                        item_type=PairCheckItemType.CONDITION,
                        id=1,
                    )
                ]
                result = run_pair_check(
                    self.analyzer,
                    conditions,
                    facts,
                    self.source_file,
                    self.target_file,
                    self.output,
                )
            else:
                self.console.print("[bold blue]標準分析を実行します。[/bold blue]")
                # 条件もファクトも抽出されなかった場合は標準分析を実行
                result = self.analyzer.analyze(
                    self.source_file,
                    self.target_file,
                    self.output,
                    config_path=self.config_path,
                )
                # 標準分析の結果が AnalysisResult オブジェクトとして返されるので、
                # output が None の場合はここでレポートを生成して標準出力する
                if self.output is None:
                    report = self.analyzer.report_generator.generate_report(
                        result, str(self.source_file), str(self.target_file)
                    )
                    self.console.print(Markdown(report))
                    sys.exit(0)  # 標準出力したら終了

            # 結果に応じた終了コードの設定 (output が指定された場合はここに到達)
            if hasattr(result, "overall_status"):  # ペアチェック系の結果の場合
                if result.overall_status == ComplianceStatus.COMPLIANT:
                    sys.exit(0)
                elif result.overall_status == ComplianceStatus.NON_COMPLIANT:
                    sys.exit(1)
                elif result.overall_status == ComplianceStatus.UNRELATED:
                    sys.exit(2)
                else:
                    sys.exit(3)
            elif hasattr(result, "status"):  # 標準分析の結果の場合
                if result.status == ComplianceStatus.COMPLIANT:
                    sys.exit(0)
                elif result.status == ComplianceStatus.NON_COMPLIANT:
                    sys.exit(1)
                elif result.status == ComplianceStatus.UNRELATED:
                    sys.exit(2)
                elif result.status == ComplianceStatus.UNKNOWN:
                    sys.exit(3)
                else:
                    sys.exit(4)
            else:  # 想定外の結果
                self.console.print(
                    "[bold red]エラー: 分析結果の形式が不正です。[/bold red]"
                )
                sys.exit(-2)

        except Exception as e:
            logger.exception("エラーが発生しました")
            self.console.print(f"[bold red]エラー:[/bold red] {str(e)}")
            sys.exit(-1)


@click.command()
@click.option(
    "--config",
    "-c",
    "config_path",
    required=True,
    type=click.Path(readable=True),
    help="設定ファイルのパス（必須）",
)
@click.option(
    "--source-file",
    "-s",
    required=True,
    type=click.Path(exists=True, readable=True),
    help="ソースファイル（比較元）のパス",
)
@click.option(
    "--target-file",
    "-t",
    required=True,
    type=click.Path(exists=True, readable=True),
    help="チェック対象ファイルのパス",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(writable=True),
    help="レポート出力先パス（指定しない場合は標準出力）",
)
@click.option(
    "--llm",
    "-m",
    type=click.Choice(TextComparisonAnalyzer.get_available_processors()),
    default=None,
    help="使用するLLM（デフォルト: 設定ファイルの値）",
)
@click.option("--verbose", "-v", is_flag=True, help="詳細なログを出力")
@click.option(
    "--extract-only",
    type=click.Choice(["conditions", "facts", "both"]),
    default=None,
    help="抽出のみを行う場合、どの項目を抽出するかを指定します（条件のみ、ファクトのみ、または両方）",
)
@click.option(
    "--use-existing-conditions",
    is_flag=True,
    help="既存の条件ファイルを使用し、条件の抽出処理をスキップします",
)
@click.option(
    "--use_existing_facts",
    is_flag=True,
    help="既存のファクトファイルを使用し、ファクトの抽出処理をスキップします",
)
@click.option(
    "--conditions-output",
    type=click.Path(writable=True),
    default="conditions_output.json",
    help="抽出したチェック条件の出力先パス（デフォルト: conditions_output.json）",
)
@click.option(
    "--facts-output",
    type=click.Path(writable=True),
    default="facts_output.json",
    help="抽出したファクトの出力先パス（デフォルト: facts_output.json）",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="抽出結果の確認をスキップし、常に了承する",
)
@click.option(
    "--skip-condition-extraction",
    is_flag=True,
    help="条件の抽出処理を強制的にスキップします",
)
@click.option(
    "--skip-fact-extraction",
    is_flag=True,
    help="ファクトの抽出処理を強制的にスキップします",
)
def check_command(
    config_path: str,
    source_file: str,
    target_file: str,
    output: Optional[str] = None,
    llm: Optional[str] = None,
    verbose: bool = False,
    extract_only: Optional[str] = None,
    use_existing_conditions: bool = False,
    use_existing_facts: bool = False,
    conditions_output: str = "conditions_output.json",
    facts_output: str = "facts_output.json",
    yes: bool = False,
    skip_condition_extraction: bool = False,
    skip_fact_extraction: bool = False,
):
    """
    文書分析を実行する。

    ソーステキストファイルとチェック対象ファイルを比較分析し、
    対象ファイルがソーステキストの内容に適合しているか、
    違反しているか、または無関係かを判断する。
    """
    command = CheckCommand(
        config_path,
        source_file,
        target_file,
        output,
        llm,
        verbose,
        extract_only,
        use_existing_conditions,
        use_existing_facts,
        conditions_output,
        facts_output,
        yes,
        skip_condition_extraction,
        skip_fact_extraction,
    )
    command.run()
