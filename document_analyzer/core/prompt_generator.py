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
        self, text: str, structured_blocks: List[Dict], conditions: List[Dict]
    ) -> str:
        """
        ファクト抽出用のプロンプトを取得する。
        Args:
            text: テキスト
            structured_blocks: 構造情報付きテキストブロックのリスト
            conditions: 条件のリスト。各条件はIDと内容を含む辞書形式。

        Returns:
            プロンプト
        """
        # 構造情報の要約を作成 (StructureAnalyzerを使用)
        structure_summary = self.structure_analyzer._create_structure_summary(
            structured_blocks
        )

        # プロンプトテンプレートを取得
        prompt_template = config.get_prompt_content("fact_extraction")

        # 条件リストをフォーマット
        conditions_list = "\n".join(
            [
                f"- 条件ID {cond['condition_id']}: {cond['content']}"
                for cond in conditions
            ]
        )

        # テンプレートに値を埋め込む
        prompt = prompt_template.format(
            text=text,
            structure_summary=structure_summary,
            conditions_list=conditions_list,
        )

        return prompt

    def _get_critic_prompt(
        self, original_prompt: str, llm_response: str, error_message: str
    ) -> str:
        """
        Critic LLM用のプロンプトを取得する。

        Args:
            original_prompt: 元のLLMに与えたプロンプト
            llm_response: LLMからの元の応答
            error_message: バリデーションエラーメッセージ

        Returns:
            プロンプト
        """
        prompt_template = config.get_prompt_content("critic_prompt")
        prompt = prompt_template.format(
            original_prompt=original_prompt,
            llm_response=llm_response,
            error_message=error_message,
        )
        return prompt
