"""
その他のLLMプロセッサーモジュール。
将来的に他のLLM（例: Claude, Llamaなど）を統合するためのプレースホルダー。
"""

from typing import Any, Dict, Optional

from ..core.processor import AnalysisResult
from .base import BaseLLMProcessor


class OtherLLMProcessor(BaseLLMProcessor):
    """
    その他のLLMプロセッサークラス。
    具体的な実装はここに追加する必要があります。
    """

    def __init__(self, model_config: Optional[Dict[str, Any]] = None):
        """
        初期化。
        """
        super().__init__(model_config)
        # TODO: ここに他のLLMの初期化処理を追加
        self.logger.warning("OtherLLMProcessorはまだ完全に実装されていません。")
        self.model_name = "other-llm (placeholder)"

    def call_llm(self, prompt: str) -> Dict[str, Any]:
        """
        LLM APIを呼び出す（プレースホルダー）。
        """
        self.logger.info(
            f"OtherLLMProcessorでプロンプトを処理します (ダミー): {prompt[:100]}..."
        )
        # TODO: ここに他のLLMのAPI呼び出し処理を追加
        # ダミー応答を返す
        dummy_response_text = """
## 遵守状態
unknown

## 信頼度
0.0

## 要約
このLLMプロセッサーはまだ実装されていません。

## 根拠
- ダミーの根拠1
- ダミーの根拠2

## 推奨事項
- このプロセッサーの実装を完了してください。
"""
        return {"text": dummy_response_text, "raw_response": {}}

    def parse_response(self, response: Dict[str, Any]) -> AnalysisResult:
        """
        LLM APIの応答を解析する（Baseクラスのメソッドを使用）。
        """
        self.logger.debug("OtherLLMProcessorで応答を解析します。")
        # BaseLLMProcessorのデフォルト解析を使用
        return super().parse_response(response)

    def call_critic_llm(self, prompt: str) -> Dict[str, Any]:
        """
        Critic LLMを呼び出す（プレースホルダー）。
        """
        self.logger.info(
            f"OtherLLMProcessorでCriticプロンプトを処理します (ダミー): {prompt[:100]}..."
        )
        # TODO: ここに他のLLMのAPI呼び出し処理を追加
        # ダミー応答を返す
        dummy_response_text = """
        ## 修正提案
        - 応答形式を修正しました。
        - 内容の妥当性を確認しました。
"""
        return {"text": dummy_response_text, "raw_response": {}}
