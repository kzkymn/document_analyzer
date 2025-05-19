from typing import Dict, List

from document_analyzer.utils.config import config

# 必要に応じて他のインポートも追加


class PromptGenerator:
    """プロンプト生成クラス"""

    def __init__(self, logger, structure_analyzer):
        self.logger = logger
        self.structure_analyzer = (
            structure_analyzer  # StructureAnalyzerのインスタンスを受け取る
        )

    def _get_condition_extraction_prompt(
        self, text: str, structured_blocks: List[Dict]
    ) -> str:
        """
        チェック条件抽出用のプロンプトを取得する。

        Args:
            text: テキスト
            structured_blocks: 構造情報付きテキストブロックのリスト

        Returns:
            プロンプト
        """
        # 構造情報の要約を作成 (StructureAnalyzerを使用)
        structure_summary = self.structure_analyzer._create_structure_summary(
            structured_blocks
        )

        # プロンプトテンプレートを取得
        prompt_template = config.get_prompt_content("condition_extraction")

        # テンプレートに値を埋め込む
        prompt = prompt_template.format(text=text, structure_summary=structure_summary)

        return prompt

    def _get_fact_extraction_prompt(
        self, text: str, structured_blocks: List[Dict]
    ) -> str:
        """
        ファクト抽出用のプロンプトを取得する。
        Args:
            text: テキスト
            structured_blocks: 構造情報付きテキストブロックのリスト

        Returns:
            プロンプト
        """
        # 構造情報の要約を作成 (StructureAnalyzerを使用)
        structure_summary = self.structure_analyzer._create_structure_summary(
            structured_blocks
        )

        # プロンプトテンプレートを取得
        prompt_template = config.get_prompt_content("fact_extraction")

        # テンプレートに値を埋め込む
        prompt = prompt_template.format(text=text, structure_summary=structure_summary)

        return prompt
