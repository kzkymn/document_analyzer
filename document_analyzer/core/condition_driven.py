import json
import re
from pathlib import Path
from typing import List, Optional, Tuple, Union

from ..llm.base import BaseLLMProcessor
from .pair_check import PairCheckItem, PairCheckItemType
from .prompt_generator import PromptGenerator
from .response_parser import ResponseParser
from .structure_analyzer import StructureAnalyzer


class ConditionDrivenExtractor:
    """条件駆動型ファクト抽出クラス"""

    def __init__(self, llm_processor: BaseLLMProcessor, logger):
        self.llm_processor = llm_processor
        self.logger = logger
        self.prompt_generator = PromptGenerator(
            self.logger, StructureAnalyzer(self.logger)
        )
        self.response_parser = ResponseParser(self.logger)

    def extract_facts_from_text(
        self, text: str, conditions: List[PairCheckItem], source: Optional[str] = None
    ) -> List[PairCheckItem]:
        """
        与えられた条件に基づいてテキストからファクトを抽出する。

        Args:
            text: ファクトを抽出する対象テキスト
            conditions: 抽出の基準となる条件のリスト
            source: 出典（ファイルパスなど）

        Returns:
            抽出されたファクトのリスト
        """
        self.logger.info("条件駆動型ファクト抽出を開始します。")
        extracted_facts = []

        # 条件をトークン長に基づいてバッチに分割
        condition_batches = []
        current_batch = []
        current_token_count = len(text) // 4  # テキストのトークン数（概算）
        token_limit = 8192  # Geminiの出力トークン制限

        if conditions:
            for condition in conditions:
                condition_token_count = (
                    len(condition.text) // 4
                )  # 条件のトークン数（概算）
                if (
                    current_token_count + condition_token_count > token_limit
                    and current_batch
                ):
                    condition_batches.append(current_batch)
                    current_batch = []
                    current_token_count = len(text) // 4
                current_batch.append(condition)
                current_token_count += condition_token_count

        if current_batch:
            condition_batches.append(current_batch)

        self.logger.info(f"{len(condition_batches)} バッチに分割して処理します。")

        for batch_idx, batch in enumerate(condition_batches):
            self.logger.info(
                f"バッチ {batch_idx + 1}/{len(condition_batches)} を処理中..."
            )

            # 条件リストを準備
            condition_list = [
                {"condition_id": cond.id, "content": cond.text} for cond in batch
            ]

            # ファクト抽出プロンプトを生成
            structured_blocks = (
                self.prompt_generator.structure_analyzer._analyze_document_structure(
                    text
                )
            )
            prompt = self.prompt_generator._get_fact_extraction_prompt(
                text, structured_blocks, condition_list
            )

            # LLMを呼び出し
            llm_response = self.llm_processor.call_llm(prompt)

            try:
                # 応答をパースしてバリデーション
                facts_dict = self.response_parser._parse_extraction_response(
                    llm_response
                )
            except ValueError as e:
                self.logger.warning(
                    f"LLM応答のバリデーションに失敗しました: {e}。再試行します。"
                )
                # 再試行のためにLLMを再度呼び出す
                llm_response = self.llm_processor.call_llm(prompt)
                try:
                    facts_dict = self.response_parser._parse_extraction_response(
                        llm_response
                    )
                    self.logger.info("LLM再試行による修正が成功しました。")
                except ValueError as retry_e:
                    self.logger.warning(
                        f"LLM再試行でもバリデーションに失敗しました: {retry_e}。Critic LLMを呼び出します。"
                    )
                    # Critic LLMを呼び出して修正を試みる
                    critic_prompt = self.prompt_generator._get_critic_prompt(
                        original_prompt=prompt,
                        llm_response=llm_response.get("text", ""),
                        error_message=str(retry_e),
                    )
                    critic_response = self.llm_processor.call_critic_llm(critic_prompt)
                    self.logger.info("Critic LLMによる修正応答を受信しました。")
                    try:
                        # 修正された応答を再度パースしてバリデーション
                        facts_dict = self.response_parser._parse_extraction_response(
                            critic_response
                        )
                        self.logger.info("Critic LLMによる修正が成功しました。")
                    except ValueError as critic_e:
                        self.logger.error(
                            f"Critic LLMによる修正後もバリデーションに失敗しました: {critic_e}"
                        )
                        self.logger.error(
                            "このバッチに対するファクト抽出をスキップします。"
                        )
                        continue  # このバッチに対する処理をスキップ

            # PairCheckItemのリストに変換
            for fact in facts_dict:
                item = PairCheckItem(
                    text=fact.text,
                    source=source,
                    item_type=PairCheckItemType.FACT,
                    id=fact.id,
                    condition_ids=fact.condition_ids,
                )
                extracted_facts.append(item)

        self.logger.info(f"{len(extracted_facts)}個のファクトを抽出しました。")
        return extracted_facts

    def save_condition_driven_facts_to_file(
        self,
        condition_facts: List[Tuple[PairCheckItem, List[PairCheckItem]]],
        output_path: Union[str, Path],
    ):
        """
        条件駆動型のファクト抽出結果をファイルに保存する。

        Args:
            condition_facts: 条件とそれに関連するファクトのリストのタプルのリスト
            output_path: 出力先ファイルのパス
        """
        path = Path(output_path)

        # 親ディレクトリが存在しない場合は作成
        path.parent.mkdir(parents=True, exist_ok=True)

        # 条件駆動型のファクト抽出結果をJSON形式に変換
        result_json = []
        for condition, facts in condition_facts:
            condition_dict = {
                "id": condition.id,
                "text": condition.text,
                "type": condition.item_type.value,
                "facts": [],
            }
            if condition.source:
                condition_dict["source"] = condition.source

            # ファクトを追加
            for fact in facts:
                fact_dict = {
                    "id": fact.id,
                    "text": fact.text,
                    "parent_id": fact.parent_id,
                    "type": fact.item_type.value,
                }
                if fact.source:
                    fact_dict["source"] = fact.source
                condition_dict["facts"].append(fact_dict)

            result_json.append(condition_dict)

        # JSONファイルとして保存
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result_json, f, ensure_ascii=False, indent=2)

        self.logger.info(
            f"条件駆動型のファクト抽出結果をJSON形式で保存しました: {path}"
        )
