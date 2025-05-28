"""
テキスト比較分析モジュール。
参照テキストと対象ファイルを比較分析するメインクラスを提供する。
"""

from pathlib import Path
from typing import Dict, Optional, Type, Union

from ..llm.gemini import GeminiProcessor
from ..llm.openai import OpenAIProcessor
from ..utils.config import config
from ..utils.logging import logger
from .processor import AnalysisResult, LLMProcessor
from .report import ReportGenerator


class TextComparisonAnalyzer:
    """テキスト比較分析クラス"""

    # 利用可能なLLMプロセッサーの辞書
    PROCESSORS: Dict[str, Type[LLMProcessor]] = {
        "gemini": GeminiProcessor,
        "openai": OpenAIProcessor,
    }

    def __init__(self, llm_name: Optional[str] = None):
        """
        初期化

        Args:
            llm_name: 使用するLLM名。指定されない場合は設定ファイルから取得。
        """
        self.logger = logger

        # 使用するLLM名を取得
        self.llm_name = llm_name or config.get("llm.default", "gemini")

        # LLMプロセッサーを初期化
        if self.llm_name not in self.PROCESSORS:
            raise ValueError(f"サポートされていないLLM: {self.llm_name}")

        self.processor = self.PROCESSORS[self.llm_name]()
        self.logger.info(f"テキスト比較分析器を初期化しました: {self.llm_name}")

        # レポート生成器を初期化
        self.report_generator = ReportGenerator()

    def analyze(
        self,
        reference_text: Union[str, Path],
        target_file: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        config_path: Optional[str] = None,
    ) -> AnalysisResult:
        """
        参照テキストと対象ファイルを比較分析する。

        Args:
            reference_text: 参照テキスト（ソーステキストなど）またはそのファイルパス
            target_file: 分析対象ファイルのパス
            output_path: レポート出力先パス。指定されない場合はレポートを生成しない。
            config_path: 設定ファイルのパス

        Returns:
            分析結果
        """
        self.logger.info(f"分析開始: {reference_text} と {target_file}")

        # 参照テキストがファイルパスの場合は読み込む
        if isinstance(reference_text, (str, Path)) and Path(reference_text).is_file():
            with open(reference_text, "r", encoding="utf-8") as f:
                reference_content = f.read()
        else:
            reference_content = str(reference_text)

        # 分析を実行（設定ファイルのパスを渡す）
        result = self.processor.process(
            reference_content, target_file, config_path=config_path
        )

        # レポートを生成（指定されている場合）
        if output_path:
            report = self.report_generator.generate_report(
                result, str(reference_text), str(target_file)
            )
            self.report_generator.save_report(report, output_path)

        self.logger.info(f"分析完了: {reference_text} と {target_file}")
        return result

    def analyze_pairs(
        self,
        source_file: Union[str, Path],
        target_file: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        config_path: Optional[str] = None,
    ) -> "PairCheckResult":
        """
        ソースファイルからチェック条件を抽出し、ターゲットファイルからファクトを抽出して、
        全ての組み合わせを検証する。

        Args:
            source_file: ソースファイルのパス
            target_file: ターゲットファイルのパス
            output_path: レポート出力先パス。指定されない場合はレポートを生成しない。
            config_path: 設定ファイルのパス

        Returns:
            ペアチェック結果
        """
        self.logger.info(f"ペアチェック分析開始: {source_file} と {target_file}")

        # ソースファイルを読み込む
        with open(source_file, "r", encoding="utf-8") as f:
            source_content = f.read()

        # ターゲットファイルを読み込む
        with open(target_file, "r", encoding="utf-8") as f:
            target_content = f.read()

        # テキスト抽出器を初期化
        from .extractor import TextExtractor

        extractor = TextExtractor(self.processor)

        # チェック条件を抽出
        conditions = extractor.extract_conditions(source_content, str(source_file))

        # ファクトを抽出
        facts = extractor.extract_facts(target_content, str(target_file))

        # ペアチェックを実行
        result = self.check_pairs(
            conditions, facts, output_path, str(source_file), str(target_file)
        )

        self.logger.info(f"ペアチェック分析完了: {source_file} と {target_file}")
        return result

    def check_pairs(
        self,
        conditions: list,
        facts: list,
        output_path: Optional[Union[str, Path]] = None,
        source_file: str = "",
        target_file: str = "",
    ) -> "PairCheckResult":
        """
        抽出済みの条件とファクトを受け取り、全ての組み合わせを検証する。

        Args:
            conditions: チェック条件のリスト
            facts: ファクトのリスト
            output_path: レポート出力先パス。指定されない場合はレポートを生成しない。
            source_file: ソースファイルのパス（レポート用）
            target_file: ターゲットファイルのパス（レポート用）

        Returns:
            ペアチェック結果
        """
        self.logger.info("ペアチェック実行開始")

        # ペアチェッカーを初期化
        from .pair_checker import PairChecker

        checker = PairChecker(self.processor)

        # ペアをチェック
        result = checker.check_pairs(conditions, facts)

        # レポートを生成（指定されている場合）
        if output_path:
            report = self.report_generator.generate_pair_check_report(
                result, source_file, target_file
            )
            self.report_generator.save_report(report, output_path)

        self.logger.info("ペアチェック実行完了")
        return result

    @classmethod
    def register_processor(cls, name: str, processor_class: Type[LLMProcessor]) -> None:
        """
        新しいLLMプロセッサーを登録する。

        Args:
            name: LLM名
            processor_class: LLMプロセッサークラス
        """
        cls.PROCESSORS[name] = processor_class
        logger.info(f"LLMプロセッサーを登録しました: {name}")

    @classmethod
    def get_available_processors(cls) -> list:
        """
        利用可能なLLMプロセッサーのリストを取得する。

        Returns:
            利用可能なLLMプロセッサー名のリスト
        """
        return list(cls.PROCESSORS.keys())
