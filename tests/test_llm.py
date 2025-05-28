"""
LLMモジュールのテスト
"""

import os
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from unittest import mock

import yaml

from document_analyzer.core.processor import (
    AnalysisResult,
    ComplianceStatus,
    Evidence,
    Recommendation,
)
from document_analyzer.llm.base import BaseLLMProcessor
from document_analyzer.llm.gemini import GeminiProcessor


# テスト用のBaseLLMProcessorのモッククラス
class MockLLMProcessor(BaseLLMProcessor):
    """テスト用のLLMプロセッサーモッククラス"""

    def call_llm(self, prompt: str) -> Dict[str, Any]:
        """
        LLMを呼び出す（モック実装）。

        Args:
            prompt: プロンプト

        Returns:
            LLMからの応答
        """
        return {"text": "モックレスポンス"}

    def parse_response(self, response: Dict[str, Any]) -> AnalysisResult:
        """
        LLMの応答を解析する（モック実装）。

        Args:
            response: LLMからの応答

        Returns:
            分析結果
        """
        return AnalysisResult(
            status=ComplianceStatus.COMPLIANT,
            confidence_score=1.0,
            summary="モックサマリー",
            evidence=[Evidence(text="モック根拠")],
            recommendations=[],
        )

    def call_critic_llm(self, prompt: str) -> Dict[str, Any]:
        """
        Critic LLMを呼び出す（モック実装）。
        """
        return {"text": "モッククリティックレスポンス"}


class TestBaseLLMProcessor(unittest.TestCase):
    """BaseLLMProcessorのテスト"""

    def test_generate_prompt_from_template(self):
        """テンプレートファイルからプロンプトを生成できることをテスト"""
        # 一時的なテンプレートファイルを作成
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_template:
            template_content = (
                "テスト参照: {reference_text}\nテスト対象: {file_content}"
            )
            temp_template.write(template_content.encode("utf-8"))

        # 一時的な設定ファイルを作成
        with tempfile.NamedTemporaryFile(
            suffix=".yaml", mode="w", delete=False
        ) as temp_config:
            config_data = {
                "prompt": {
                    "template_path": temp_template.name,
                    "description": "テスト用設定",
                },
                "logging": {"level": "INFO"},
                "llm": {
                    "default": "gemini",
                    "models": {"gemini": {"model_name": "gemini-2.0-flash"}},
                },
            }
            yaml.dump(config_data, temp_config, default_flow_style=False)

        try:
            # テスト用のプロセッサーを作成
            processor = MockLLMProcessor()

            # プロンプトを生成
            prompt = processor.generate_prompt(
                "参照テキスト", "ファイル内容", config_path=temp_config.name
            )

            # 生成されたプロンプトを確認
            self.assertIn("テスト参照: 参照テキスト", prompt)
            self.assertIn("テスト対象: ファイル内容", prompt)

        finally:
            # 一時ファイルを削除
            os.unlink(temp_template.name)
            os.unlink(temp_config.name)

    def test_generate_prompt_template_not_found(self):
        """テンプレートファイルが見つからない場合にデフォルトのプロンプトを使用することをテスト"""
        # 一時的な設定ファイルを作成
        with tempfile.NamedTemporaryFile(
            suffix=".yaml", mode="w", delete=False
        ) as temp_config:
            config_data = {
                "prompt": {
                    "template_path": "non_existent_template.txt",
                    "description": "テスト用設定",
                },
                "logging": {"level": "INFO"},
                "llm": {
                    "default": "gemini",
                    "models": {"gemini": {"model_name": "gemini-2.0-flash"}},
                },
            }
            yaml.dump(config_data, temp_config, default_flow_style=False)

        try:
            # テスト用のプロセッサーを作成
            processor = MockLLMProcessor()

            # プロンプトを生成
            prompt = processor.generate_prompt(
                "参照テキスト", "ファイル内容", config_path=temp_config.name
            )

            # デフォルトのプロンプトが使用されることを確認
            self.assertIn("参照テキスト", prompt)
            self.assertIn("ファイル内容", prompt)

        finally:
            # 一時ファイルを削除
            os.unlink(temp_config.name)


class TestGeminiProcessor(unittest.TestCase):
    """GeminiProcessorのテスト"""

    def setUp(self):
        """テスト前の準備"""
        self.test_dir = Path(__file__).parent
        self.test_data_dir = self.test_dir / "test_data"
        self.compliant_doc_path = self.test_data_dir / "compliant_report.txt"

        # テスト用の一時ファイル
        self.temp_file_path = self.test_dir / "temp_test_file.txt"
        with open(self.temp_file_path, "w", encoding="utf-8") as f:
            f.write("テスト用のコンテンツ")

        # テスト後に削除するファイル
        self.files_to_delete = [self.temp_file_path]

        # APIキーのモック
        self.api_key_patcher = mock.patch(
            "document_analyzer.utils.config.config.get_gemini_api_key"
        )
        self.mock_get_api_key = self.api_key_patcher.start()
        self.mock_get_api_key.return_value = "mock_api_key"

        # Gemini APIのモック
        self.genai_patcher = mock.patch("google.generativeai.GenerativeModel")
        self.mock_genai = self.genai_patcher.start()
        self.mock_model = mock.MagicMock()
        self.mock_genai.return_value = self.mock_model

        # list_modelsのモック
        self.list_models_patcher = mock.patch("google.generativeai.list_models")
        self.mock_list_models = self.list_models_patcher.start()
        self.mock_list_models.return_value = []

    def tearDown(self):
        """テスト後のクリーンアップ"""
        for file_path in self.files_to_delete:
            if file_path.exists():
                file_path.unlink()

        # モックを停止
        self.api_key_patcher.stop()
        self.genai_patcher.stop()
        self.list_models_patcher.stop()

    def test_initialization(self):
        """初期化のテスト"""
        processor = GeminiProcessor()
        self.assertEqual(processor.model_name, "gemini-2.0-flash")
        self.assertIsNotNone(processor.model)

    def test_preprocess_reference_text(self):
        """参照テキスト前処理のテスト"""
        processor = GeminiProcessor()

        # 空白行や余分な空白を含むテキスト
        text = """
        これは
        
        テスト用の
          テキストです。
        
        """

        processed_text = processor.preprocess_reference_text(text)

        # 空白行が削除され、各行の余分な空白が削除されていることを確認
        expected = "これは\nテスト用の\nテキストです。"
        self.assertEqual(processed_text, expected)

    def test_preprocess_file(self):
        """ファイル前処理のテスト"""
        processor = GeminiProcessor()

        # 存在するファイルの前処理
        content = processor.preprocess_file(self.temp_file_path)
        self.assertEqual(content, "テスト用のコンテンツ")

        # 存在しないファイルの前処理
        non_existent_file = self.test_dir / "non_existent_file.txt"
        with self.assertRaises(FileNotFoundError):
            processor.preprocess_file(non_existent_file)

    def test_generate_prompt(self):
        """プロンプト生成のテスト"""
        processor = GeminiProcessor()

        reference_text = "参照テキスト"
        file_content = "ファイル内容"

        prompt = processor.generate_prompt(reference_text, file_content)

        # プロンプトに必要な要素が含まれていることを確認
        self.assertIn("参照テキスト", prompt)
        self.assertIn("ファイル内容", prompt)
        self.assertIn("遵守状態", prompt)
        self.assertIn("信頼度", prompt)
        self.assertIn("要約", prompt)
        self.assertIn("根拠", prompt)
        self.assertIn("推奨事項", prompt)

    @mock.patch("document_analyzer.llm.gemini.GeminiProcessor.call_llm")
    def test_process(self, mock_call_llm):
        """処理フローのテスト"""
        # LLM呼び出しをモック
        mock_response = {
            "text": """
## 遵守状態
compliant

## 信頼度
0.95

## 要約
対象文書はソーステキストに記載されている要件を満たしています。

## 根拠
- 根拠1: 対象文書では個人情報の定義がソーステキストと一致している
- 根拠2: 個人情報の取得方法が適法かつ公正な手段と明記されている

## 推奨事項
- 推奨事項1: 特になし
"""
        }
        mock_call_llm.return_value = mock_response

        processor = GeminiProcessor()
        result = processor.process("参照テキスト", self.temp_file_path)

        # 結果を検証
        self.assertEqual(result.status, ComplianceStatus.COMPLIANT)
        self.assertAlmostEqual(result.confidence_score, 0.95)
        self.assertEqual(len(result.evidence), 2)
        self.assertEqual(len(result.recommendations), 1)

    def test_parse_response_valid(self):
        """有効な応答の解析テスト"""
        processor = GeminiProcessor()

        # 有効な応答
        response = {
            "text": """
## 遵守状態
compliant

## 信頼度
0.95

## 要約
対象文書はソーステキストに記載されている要件を満たしています。

## 根拠
- 根拠1: 対象文書では個人情報の定義がソーステキストと一致している
- 根拠2: 個人情報の取得方法が適法かつ公正な手段と明記されている

## 推奨事項
- 推奨事項1: 特になし
"""
        }

        result = processor.parse_response(response)

        # 結果を検証
        self.assertEqual(result.status, ComplianceStatus.COMPLIANT)
        self.assertAlmostEqual(result.confidence_score, 0.95)
        self.assertIn("対象文書はソーステキスト", result.summary)
        self.assertEqual(len(result.evidence), 2)
        self.assertEqual(len(result.recommendations), 1)

    def test_parse_response_invalid(self):
        """無効な応答の解析テスト"""
        processor = GeminiProcessor()

        # 完全に無効な応答（ValidationErrorを発生させるため、textキーがない）
        response = {"error": "Invalid response"}

        result = processor.parse_response(response)

        # エラー時のフォールバック値を検証
        self.assertEqual(result.status, ComplianceStatus.UNKNOWN)
        self.assertAlmostEqual(result.confidence_score, 0.0)
        # 実際の実装では、summary は空文字列になる
        self.assertEqual(result.summary, "")
        self.assertEqual(len(result.evidence), 0)
        self.assertEqual(len(result.recommendations), 0)


if __name__ == "__main__":
    unittest.main()
