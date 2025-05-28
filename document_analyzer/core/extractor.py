"""
テキスト抽出モジュール。
テキストから条件やファクトを抽出するクラスを提供する。
"""

from typing import Dict, List, Optional

from ..llm.base import BaseLLMProcessor
from .condition_driven import ConditionDrivenExtractor
from .file_handler import FileHandler
from .pair_check import PairCheckItem, PairCheckItemType
from .prompt_generator import PromptGenerator
from .response_parser import ResponseParser

# Import the new classes
from .structure_analyzer import StructureAnalyzer


class TextExtractor:
    """テキスト抽出クラス"""

    def __init__(self, llm_processor: BaseLLMProcessor):
        """
        初期化

        Args:
            llm_processor: LLMプロセッサー
        """
        self.llm_processor = llm_processor
        self.logger = llm_processor.logger
        # Initialize instances of the new helper classes
        self.structure_analyzer = StructureAnalyzer(self.logger)
        self.response_parser = ResponseParser(self.logger)
        self.prompt_generator = PromptGenerator(
            self.logger, self.structure_analyzer
        )  # PromptGenerator needs StructureAnalyzer
        self.file_handler = FileHandler(self.logger)
        self.condition_driven_extractor = ConditionDrivenExtractor(
            self.llm_processor, self.logger
        )  # ConditionDrivenExtractor needs llm_processor and logger

    def extract_conditions(
        self, text: str, source: Optional[str] = None
    ) -> List[PairCheckItem]:
        """
        テキストからチェック条件を抽出する。

        Args:
            text: テキスト
            source: 出典（ファイルパスなど）

        Returns:
            チェック条件のリスト
        """
        self.logger.info("チェック条件の抽出を開始します")

        # チャンク処理の判断
        if self.structure_analyzer.should_chunk_text(text):
            self.logger.info("テキストが長いため、チャンクに分割して条件を抽出します。")
            chunks = self.structure_analyzer.chunk_text(text)
            all_conditions = []
            for i, chunk in enumerate(chunks):
                self.logger.info(f"チャンク {i+1}/{len(chunks)} から条件を抽出中...")
                structured_blocks = self.structure_analyzer._analyze_document_structure(
                    chunk
                )
                prompt = self.prompt_generator._get_condition_extraction_prompt(
                    chunk, structured_blocks
                )
                response = self.llm_processor.call_llm(prompt)
                conditions_dict = self.response_parser._parse_extraction_response(
                    response
                )
                all_conditions.extend(conditions_dict)
            conditions_dict = all_conditions
        else:
            self.logger.info(
                "テキストが短いため、単一のLLM呼び出しで条件を抽出します。"
            )
            # 文書構造を解析 (Use StructureAnalyzer)
            structured_blocks = self.structure_analyzer._analyze_document_structure(
                text
            )
            # LLMを使用して条件を抽出 (Use PromptGenerator and ResponseParser)
            prompt = self.prompt_generator._get_condition_extraction_prompt(
                text, structured_blocks
            )
            response = self.llm_processor.call_llm(prompt)
            conditions_dict = self.response_parser._parse_extraction_response(response)

        # PairCheckItemのリストに変換
        result = []
        for (
            condition
        ) in (
            conditions_dict
        ):  # conditions_dictはPairCheckItemのリストであるため、辞書アクセスではなく属性アクセスに変更
            item = PairCheckItem(
                text=condition.text,
                source=source,
                item_type=PairCheckItemType.CONDITION,
                id=condition.id,
                parent_id=condition.parent_id,
            )
            result.append(item)

        # 後処理ロジックの呼び出し
        result = self.response_parser._post_process_extracted_items(result)

        # 親子関係を設定
        for item in result:
            if item.parent_id is not None:
                # 親アイテムを探す
                parent = next((p for p in result if p.id == item.parent_id), None)
                if parent:
                    if parent.children is None:
                        parent.children = []
                    parent.children.append(item)

        self.logger.info(f"{len(result)}個のチェック条件を抽出しました")
        return result

    def extract_facts(
        self,
        text: str,
        conditions: List[PairCheckItem],  # 新しく追加する引数
        source: Optional[str] = None,
    ) -> List[PairCheckItem]:
        """
        テキストからファクトを抽出する。

        Args:
            text: テキスト
            source: 出典（ファイルパスなど）

        Returns:
            ファクトのリスト
        """
        self.logger.info("ファクトの抽出を開始します")

        # チャンク処理の判断
        if self.structure_analyzer.should_chunk_text(text):
            self.logger.info(
                "テキストが長いため、チャンクに分割してファクトを抽出します。"
            )
            chunks = self.structure_analyzer.chunk_text(text)
            all_facts = []
            for i, chunk in enumerate(chunks):
                self.logger.info(
                    f"チャンク {i+1}/{len(chunks)} からファクトを抽出中..."
                )
                # ConditionDrivenExtractorを強制適用
                facts_dict = self.condition_driven_extractor.extract_facts_from_text(
                    chunk, conditions, source
                )
                all_facts.extend(facts_dict)
            facts_dict = all_facts
        else:
            self.logger.info(
                "テキストが短いため、単一のLLM呼び出しでファクトを抽出します。"
            )
            # ConditionDrivenExtractorを強制適用
            facts_dict = self.condition_driven_extractor.extract_facts_from_text(
                text, conditions, source
            )

        # PairCheckItemのリストに変換
        result = []
        for fact in facts_dict:
            item = PairCheckItem(
                text=fact.text,
                source=source,
                item_type=PairCheckItemType.FACT,
                id=fact.id,
                parent_id=fact.parent_id,
            )
            result.append(item)

        # 後処理ロジックの呼び出し
        result = self.response_parser._post_process_extracted_items(result)

        # 親子関係を設定
        for item in result:
            if item.parent_id is not None:
                # 親アイテムを探す
                parent = next((p for p in result if p.id == item.parent_id), None)
                if parent:
                    if parent.children is None:
                        parent.children = []
                    parent.children.append(item)

        self.logger.info(f"{len(result)}個のファクトを抽出しました")
        return result
