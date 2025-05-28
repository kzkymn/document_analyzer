"""
コア機能のテスト
"""

import os
import unittest
from pathlib import Path
from unittest import mock

from document_analyzer.core.analyzer import TextComparisonAnalyzer
from document_analyzer.core.extractor import TextExtractor
from document_analyzer.core.pair_check import PairCheckItem, PairCheckItemType
from document_analyzer.core.pair_checker import PairChecker
from document_analyzer.core.processor import (
    AnalysisResult,
    ComplianceStatus,
    Evidence,
    LLMProcessor,
    Recommendation,
)
from document_analyzer.core.report import ReportGenerator


class TestTextComparisonAnalyzer(unittest.TestCase):
    """TextComparisonAnalyzerのテスト"""

    def setUp(self):
        """テスト前の準備"""
        self.test_dir = Path(__file__).parent
        # テストデータはsample_inputディレクトリにあるためパスを修正
        self.source_text_path = (
            self.test_dir.parent
            / "sample_input"
            / "weekly_report_check"
            / "writing_guidelines.txt"
        )
        self.compliant_doc_path = (
            self.test_dir.parent
            / "sample_input"
            / "weekly_report_check"
            / "compliant_report.txt"
        )
        self.non_compliant_doc_path = (
            self.test_dir.parent
            / "sample_input"
            / "weekly_report_check"
            / "non_compliant_report.txt"
        )
        # unrelated_document.txt は sample_input/compliance_check にあるためパスを修正 (テストから除外)

        # テスト用のレポート出力先
        self.report_path = self.test_dir / "test_report.md"

        # テスト後に削除するファイル
        self.files_to_delete = [self.report_path]

    def tearDown(self):
        """テスト後のクリーンアップ"""
        for file_path in self.files_to_delete:
            if file_path.exists():
                file_path.unlink()

    def test_initialization(self):
        """初期化のテスト"""
        analyzer = TextComparisonAnalyzer()
        self.assertEqual(analyzer.llm_name, "gemini")
        self.assertIsNotNone(analyzer.processor)
        self.assertIsNotNone(analyzer.report_generator)

    def test_file_reading(self):
        """ファイル読み込みのテスト"""
        # 各ファイルが存在することを確認
        self.assertTrue(self.source_text_path.exists())
        self.assertTrue(self.compliant_doc_path.exists())
        self.assertTrue(self.non_compliant_doc_path.exists())

        # ファイルの内容を読み込めることを確認
        with open(self.source_text_path, "r", encoding="utf-8") as f:
            source_text = f.read()
        self.assertIn("プログラマ週次報告書 執筆ガイドライン", source_text)

        with open(self.compliant_doc_path, "r", encoding="utf-8") as f:
            compliant_doc = f.read()
        self.assertIn("ECサイトリニューアル案件", compliant_doc)

        with open(self.non_compliant_doc_path, "r", encoding="utf-8") as f:
            non_compliant_doc = f.read()
        self.assertIn("鈴木一郎です。今週の報告です。", non_compliant_doc)

    @mock.patch("document_analyzer.llm.gemini.GeminiProcessor.call_llm")
    def test_analyze_with_mock(self, mock_call_llm):
        """モックを使用した分析のテスト"""
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
- 根拠3: 利用目的の明示と同意取得が規定されている

## 推奨事項
- 推奨事項1: 特になし
"""
        }
        mock_call_llm.return_value = mock_response

        # 分析を実行
        analyzer = TextComparisonAnalyzer()
        result = analyzer.analyze(
            self.source_text_path, self.compliant_doc_path, self.report_path
        )

        # 結果を検証
        self.assertEqual(result.status, ComplianceStatus.COMPLIANT)
        self.assertAlmostEqual(result.confidence_score, 0.95)
        self.assertEqual(len(result.evidence), 3)
        self.assertEqual(len(result.recommendations), 1)

        # レポートが生成されたことを確認
        self.assertTrue(self.report_path.exists())
        with open(self.report_path, "r", encoding="utf-8") as f:
            report_content = f.read()
        self.assertIn("文書分析レポート", report_content)
        self.assertIn("遵守状態", report_content)

    def test_report_generator(self):
        """レポート生成のテスト"""
        # テスト用の分析結果を作成
        result = AnalysisResult(
            status=ComplianceStatus.NON_COMPLIANT,  # 推奨事項をテストするためにNON_COMPLIANTに変更
            confidence_score=0.9,
            summary="テスト用の要約",
            evidence=[
                Evidence(text="テスト用の根拠1"),
                Evidence(text="テスト用の根拠2"),
            ],
            recommendations=[Recommendation(text="テスト用の推奨事項")],
        )

        # レポートを生成
        report_generator = ReportGenerator()
        report = report_generator.generate_report(
            result, str(self.source_text_path), str(self.compliant_doc_path)
        )

        # レポートの内容を検証
        self.assertIn("文書分析レポート", report)
        self.assertIn("遵守状態", report)
        self.assertIn("テスト用の要約", report)
        self.assertIn("テスト用の根拠1", report)
        self.assertIn("テスト用の根拠2", report)
        self.assertIn("テスト用の推奨事項", report)

        # レポートを保存
        saved_path = report_generator.save_report(report, self.report_path)
        self.assertEqual(saved_path, self.report_path)
        self.assertTrue(self.report_path.exists())

    def test_analyze_with_invalid_file(self):
        """存在しないファイルを指定した場合のテスト"""
        analyzer = TextComparisonAnalyzer()
        non_existent_file = self.test_dir / "non_existent_file.txt"

        # 存在しないファイルを指定した場合、FileNotFoundErrorが発生することを確認
        with self.assertRaises(FileNotFoundError):
            analyzer.analyze(self.source_text_path, non_existent_file, self.report_path)

    def test_analyze_with_empty_reference(self):
        """空の参照テキストを指定した場合のテスト"""
        # 空の一時ファイルを作成
        empty_reference_path = self.test_dir / "empty_reference.txt"
        with open(empty_reference_path, "w", encoding="utf-8") as f:
            f.write("")

        self.files_to_delete.append(empty_reference_path)

        analyzer = TextComparisonAnalyzer()

        # モックを使用してLLM呼び出しをシミュレート
        with mock.patch(
            "document_analyzer.llm.gemini.GeminiProcessor.call_llm"
        ) as mock_call_llm:
            mock_response = {
                "text": """
## 遵守状態
unknown

## 信頼度
0.5

## 要約
参照テキストが空のため、適切な分析ができません。

## 根拠
- 根拠1: 参照テキストが提供されていない

## 推奨事項
- 推奨事項1: 有効な参照テキストを提供してください
"""
            }
            mock_call_llm.return_value = mock_response

            # 分析を実行
            result = analyzer.analyze(
                empty_reference_path, self.compliant_doc_path, self.report_path
            )

            # 結果を検証
            self.assertEqual(result.status, ComplianceStatus.UNKNOWN)
            self.assertAlmostEqual(result.confidence_score, 0.5)
            self.assertIn("参照テキストが空のため", result.summary)

    def test_register_processor(self):
        """プロセッサー登録機能のテスト"""

        # テスト用のモッククラスを作成
        class MockProcessor(LLMProcessor):
            def preprocess_reference_text(self, text):
                return text

            def preprocess_file(self, file_path):
                return "Mock content"

            def generate_prompt(self, reference_text, file_content):
                return "Mock prompt"

            def call_llm(self, prompt):
                return {"text": "Mock response"}

            def parse_response(self, response):
                return AnalysisResult(
                    status=ComplianceStatus.COMPLIANT,
                    confidence_score=1.0,
                    summary="Mock summary",
                    evidence=[Evidence(text="Mock evidence")],
                    recommendations=[],
                )

            def call_critic_llm(self, prompt):
                return {"text": "Mock critic response"}

        # 登録前の利用可能なプロセッサー数を取得
        processors_before = len(TextComparisonAnalyzer.get_available_processors())

        # 新しいプロセッサーを登録
        TextComparisonAnalyzer.register_processor("mock", MockProcessor)

        # 登録後の利用可能なプロセッサー数を取得
        processors_after = len(TextComparisonAnalyzer.get_available_processors())

        # 登録されたことを確認
        self.assertEqual(processors_after, processors_before + 1)
        self.assertIn("mock", TextComparisonAnalyzer.get_available_processors())

        # 登録したプロセッサーを使用して分析器を初期化
        analyzer = TextComparisonAnalyzer(llm_name="mock")
        self.assertEqual(analyzer.llm_name, "mock")
        self.assertIsInstance(analyzer.processor, MockProcessor)


class TestTextExtractor(unittest.TestCase):
    """TextExtractorのテスト"""

    def setUp(self):
        """テスト前の準備"""
        # モックのLLMプロセッサーを作成
        self.mock_llm_processor = mock.Mock()
        self.mock_llm_processor.logger = mock.Mock()  # logger属性を追加
        self.mock_llm_processor.call_critic_llm = (
            mock.Mock()
        )  # Critic LLMのモックを追加

        # ResponseParserのモック
        self.mock_response_parser = mock.Mock()
        self.mock_response_parser._post_process_extracted_items.side_effect = (
            lambda x: x
        )  # 後処理はそのまま返す

        # StructureAnalyzerのモック
        self.mock_structure_analyzer = mock.Mock()
        self.mock_structure_analyzer._analyze_document_structure.return_value = [
            {"text": "test", "structure": {"type": "paragraph"}}
        ]
        self.mock_structure_analyzer.should_chunk_text.return_value = False
        self.mock_structure_analyzer.chunk_text.return_value = ["chunk1", "chunk2"]

        # PromptGeneratorのモック
        self.mock_prompt_generator = mock.Mock()
        self.mock_prompt_generator._get_condition_extraction_prompt.return_value = (
            "条件抽出プロンプト"
        )
        self.mock_prompt_generator._get_fact_extraction_prompt.return_value = (
            "ファクト抽出プロンプト"
        )
        self.mock_prompt_generator._get_critic_prompt.return_value = "Criticプロンプト"
        self.mock_prompt_generator.structure_analyzer = (
            self.mock_structure_analyzer
        )  # PromptGeneratorがStructureAnalyzerを持つように設定

        # TextExtractorの初期化時にモックを注入
        with mock.patch(
            "document_analyzer.core.extractor.ResponseParser",
            return_value=self.mock_response_parser,
        ), mock.patch(
            "document_analyzer.core.extractor.StructureAnalyzer",
            return_value=self.mock_structure_analyzer,
        ), mock.patch(
            "document_analyzer.core.extractor.PromptGenerator",
            return_value=self.mock_prompt_generator,
        ), mock.patch(
            "document_analyzer.core.extractor.ConditionDrivenExtractor"
        ) as MockConditionDrivenExtractor:

            # ConditionDrivenExtractorのモックインスタンスを作成し、extract_facts_from_textをモック
            self.mock_condition_driven_extractor_instance = (
                MockConditionDrivenExtractor(
                    self.mock_llm_processor, self.mock_llm_processor.logger
                ).return_value
            )
            self.mock_condition_driven_extractor_instance.extract_facts_from_text.return_value = [
                PairCheckItem(id=1, text="ファクト1", item_type=PairCheckItemType.FACT)
            ]

            self.extractor = TextExtractor(self.mock_llm_processor)
            # TextExtractorが内部で生成するインスタンスをモックに置き換える
            self.extractor.response_parser = self.mock_response_parser
            self.extractor.structure_analyzer = self.mock_structure_analyzer
            self.extractor.prompt_generator = self.mock_prompt_generator
            self.extractor.condition_driven_extractor = (
                self.mock_condition_driven_extractor_instance
            )

    def tearDown(self):
        """テスト後のクリーンアップ"""
        pass  # モックの停止は不要になった

    def test_extract_conditions_short_text(self):
        """短文からのチェック条件抽出のテスト"""
        test_text = "これは短いテキストです。"
        self.mock_llm_processor.call_llm.return_value = {
            "text": '```json\n[{"id": 1, "text": "条件1", "item_type": "condition"}]\n```'
        }
        self.mock_response_parser._parse_extraction_response.return_value = [
            PairCheckItem(id=1, text="条件1", item_type=PairCheckItemType.CONDITION)
        ]
        self.mock_structure_analyzer.should_chunk_text.return_value = False

        conditions = self.extractor.extract_conditions(test_text, "test_source.txt")

        self.assertEqual(len(conditions), 1)
        self.assertEqual(conditions[0].text, "条件1")
        self.mock_llm_processor.call_llm.assert_called_once()
        self.mock_structure_analyzer.should_chunk_text.assert_called_once_with(
            test_text
        )
        self.mock_response_parser._parse_extraction_response.assert_called_once()
        self.mock_response_parser._post_process_extracted_items.assert_called_once()

    def test_extract_conditions_long_text_with_chunking(self):
        """長文からのチェック条件抽出（チャンク分割あり）のテスト"""
        test_text = "a" * 5000  # チャンクサイズより長いテキスト
        self.mock_structure_analyzer.should_chunk_text.return_value = True
        self.mock_structure_analyzer.chunk_text.return_value = ["chunk1", "chunk2"]
        self.mock_llm_processor.call_llm.side_effect = [
            {
                "text": '```json\n[{"id": 1, "text": "条件A", "item_type": "condition"}]\n```'
            },
            {
                "text": '```json\n[{"id": 2, "text": "条件B", "item_type": "condition"}]\n```'
            },
        ]
        self.mock_response_parser._parse_extraction_response.side_effect = [
            [PairCheckItem(id=1, text="条件A", item_type=PairCheckItemType.CONDITION)],
            [PairCheckItem(id=2, text="条件B", item_type=PairCheckItemType.CONDITION)],
        ]

        conditions = self.extractor.extract_conditions(test_text, "test_source.txt")

        self.assertEqual(len(conditions), 2)
        self.assertEqual(conditions[0].text, "条件A")
        self.assertEqual(conditions[1].text, "条件B")
        self.assertEqual(self.mock_llm_processor.call_llm.call_count, 2)
        self.mock_structure_analyzer.should_chunk_text.assert_called_once_with(
            test_text
        )
        self.mock_structure_analyzer.chunk_text.assert_called_once_with(test_text)
        self.assertEqual(
            self.mock_response_parser._parse_extraction_response.call_count, 2
        )
        self.mock_response_parser._post_process_extracted_items.assert_called_once()

    def test_extract_facts_short_text(self):
        """短文からのファクト抽出のテスト"""
        test_text = "これは短いテキストです。"
        self.mock_structure_analyzer.should_chunk_text.return_value = False

        # ConditionDrivenExtractorのextract_facts_from_textが呼び出されることを確認
        # ダミーのconditionsリストを渡す
        dummy_conditions = [
            PairCheckItem(
                id=999, text="ダミー条件", item_type=PairCheckItemType.CONDITION
            )
        ]
        facts = self.extractor.extract_facts(
            test_text, dummy_conditions, "test_target.txt"
        )

        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0].text, "ファクト1")
        self.mock_condition_driven_extractor_instance.extract_facts_from_text.assert_called_once_with(
            test_text, dummy_conditions, "test_target.txt"
        )
        self.mock_structure_analyzer.should_chunk_text.assert_called_once_with(
            test_text
        )
        self.mock_response_parser._post_process_extracted_items.assert_called_once()

    def test_extract_facts_long_text_with_chunking(self):
        """長文からのファクト抽出（チャンク分割あり）のテスト"""
        test_text = "b" * 5000  # チャンクサイズより長いテキスト
        self.mock_structure_analyzer.should_chunk_text.return_value = True
        self.mock_structure_analyzer.chunk_text.return_value = ["chunk1", "chunk2"]

        # ConditionDrivenExtractorのextract_facts_from_textがチャンクごとに呼び出されることを確認
        self.mock_condition_driven_extractor_instance.extract_facts_from_text.side_effect = [
            [PairCheckItem(id=1, text="ファクトX", item_type=PairCheckItemType.FACT)],
            [PairCheckItem(id=2, text="ファクトY", item_type=PairCheckItemType.FACT)],
        ]

        # ダミーのconditionsリストを渡す
        dummy_conditions = [
            PairCheckItem(
                id=999, text="ダミー条件", item_type=PairCheckItemType.CONDITION
            )
        ]
        facts = self.extractor.extract_facts(
            test_text, dummy_conditions, "test_target.txt"
        )

        self.assertEqual(len(facts), 2)
        self.assertEqual(facts[0].text, "ファクトX")
        self.assertEqual(facts[1].text, "ファクトY")
        self.assertEqual(
            self.mock_condition_driven_extractor_instance.extract_facts_from_text.call_count,
            2,
        )
        self.mock_condition_driven_extractor_instance.extract_facts_from_text.assert_has_calls(
            [
                mock.call("chunk1", dummy_conditions, "test_target.txt"),
                mock.call("chunk2", dummy_conditions, "test_target.txt"),
            ]
        )
        self.mock_structure_analyzer.should_chunk_text.assert_called_once_with(
            test_text
        )
        self.mock_structure_analyzer.chunk_text.assert_called_once_with(test_text)
        self.mock_response_parser._post_process_extracted_items.assert_called_once()


from document_analyzer.core.condition_driven import ConditionDrivenExtractor  # 追加


class TestConditionDrivenExtractor(unittest.TestCase):
    """ConditionDrivenExtractorのテスト"""

    def setUp(self):
        self.mock_llm_processor = mock.Mock()
        self.mock_llm_processor.logger = mock.Mock()
        self.mock_llm_processor.call_llm.return_value = {
            "text": '```json\n[{"id": 1, "text": "抽出されたファクト", "item_type": "fact"}]\n```'
        }
        self.mock_llm_processor.call_critic_llm.return_value = {
            "text": '```json\n[{"id": 1, "text": "修正されたファクト", "item_type": "fact"}]\n```'
        }

        # PromptGeneratorとResponseParserのモック
        self.mock_prompt_generator = mock.Mock()
        self.mock_prompt_generator._get_fact_extraction_prompt.return_value = (
            "ファクト抽出プロンプト"
        )
        self.mock_prompt_generator._get_critic_prompt.return_value = "Criticプロンプト"
        self.mock_prompt_generator.structure_analyzer = mock.Mock()
        self.mock_prompt_generator.structure_analyzer._analyze_document_structure.return_value = [
            {"text": "test", "structure": {"type": "paragraph"}}
        ]

        self.mock_response_parser = mock.Mock()
        # _parse_extraction_responseの戻り値をPairCheckItemのリストに修正
        self.mock_response_parser._parse_extraction_response.side_effect = lambda x: [
            PairCheckItem(
                id=1, text="抽出されたファクト", item_type=PairCheckItemType.FACT
            )
        ]
        self.mock_response_parser._post_process_extracted_items.side_effect = (
            lambda x: x
        )

        # ConditionDrivenExtractorを直接モック化しない
        self.extractor = ConditionDrivenExtractor(
            self.mock_llm_processor, self.mock_llm_processor.logger
        )
        # 内部で生成されるPromptGeneratorとResponseParserのインスタンスをモックに置き換える
        self.extractor.prompt_generator = self.mock_prompt_generator
        self.extractor.response_parser = self.mock_response_parser

    def test_extract_facts_from_text_success(self):
        """条件駆動型ファクト抽出の成功テスト"""
        test_text = "これはテストテキストです。"
        conditions = [
            PairCheckItem(
                id=1, text="テスト条件", item_type=PairCheckItemType.CONDITION
            )
        ]

        facts = self.extractor.extract_facts_from_text(
            test_text, conditions, "test_source.txt"
        )

        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0].text, "抽出されたファクト")
        self.assertEqual(self.mock_llm_processor.call_llm.call_count, 1)
        self.mock_prompt_generator._get_fact_extraction_prompt.assert_called_once()
        self.mock_response_parser._parse_extraction_response.assert_called_once()
        self.mock_llm_processor.call_critic_llm.assert_not_called()

    def test_extract_facts_from_text_with_critic_retry(self):
        """条件駆動型ファクト抽出（Critic LLMによるリトライ）のテスト"""
        test_text = "これはテストテキストです。"
        conditions = [
            PairCheckItem(
                id=1, text="テスト条件", item_type=PairCheckItemType.CONDITION
            )
        ]

        # 最初のパースでエラー、再試行もエラー、Critic LLMで成功するよう設定
        self.mock_response_parser._parse_extraction_response.side_effect = [
            ValueError("JSON解析エラー (初回)"),
            ValueError("JSON解析エラー (再試行)"),
            [
                PairCheckItem(
                    id=1, text="修正されたファクト", item_type=PairCheckItemType.FACT
                )
            ],
        ]

        facts = self.extractor.extract_facts_from_text(
            test_text, conditions, "test_source.txt"
        )

        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0].text, "修正されたファクト")
        self.assertEqual(
            self.mock_llm_processor.call_llm.call_count, 2
        )  # 最初のLLM呼び出しと再試行
        self.mock_llm_processor.call_critic_llm.assert_called_once()  # Critic LLM呼び出し
        self.assertEqual(
            self.mock_response_parser._parse_extraction_response.call_count, 3
        )  # 最初のパース、再試行のパース、Critic LLMのパース

    def test_extract_facts_from_text_critic_failure(self):
        """条件駆動型ファクト抽出（Critic LLMも失敗）のテスト"""
        test_text = "これはテストテキストです。"
        conditions = [
            PairCheckItem(
                id=1, text="テスト条件", item_type=PairCheckItemType.CONDITION
            )
        ]

        # 最初のパースでエラー、再試行もエラー、Critic LLMもエラー
        self.mock_response_parser._parse_extraction_response.side_effect = [
            ValueError("JSON解析エラー (初回)"),
            ValueError("JSON解析エラー (再試行)"),
            ValueError("Critic LLMもJSON解析エラー"),
        ]

        facts = self.extractor.extract_facts_from_text(
            test_text, conditions, "test_source.txt"
        )

        self.assertEqual(len(facts), 0)  # ファクトが抽出されないことを確認
        self.assertEqual(self.mock_llm_processor.call_llm.call_count, 2)
        self.mock_llm_processor.call_critic_llm.assert_called_once()
        self.assertEqual(
            self.mock_response_parser._parse_extraction_response.call_count, 3
        )


class TestPairChecker(unittest.TestCase):
    """PairCheckerのテスト"""

    def setUp(self):
        """テスト前の準備"""
        # モックのLLMプロセッサーを作成
        self.mock_llm_processor = mock.Mock()
        self.mock_llm_processor.logger = mock.Mock()  # logger属性を追加
        self.checker = PairChecker(self.mock_llm_processor)

        # テスト用の条件とファクト
        self.condition1 = PairCheckItem(
            text="レポートは週次で提出すること",
            source="source.txt",
            item_type=PairCheckItemType.CONDITION,
        )
        self.fact1 = PairCheckItem(
            text="週次報告書を提出しました",
            source="target.txt",
            item_type=PairCheckItemType.FACT,
        )
        self.fact2 = PairCheckItem(
            text="日次報告書を提出しました",
            source="target.txt",
            item_type=PairCheckItemType.FACT,
        )

    def test_check_pairs_compliant(self):
        """ペアチェック（適合）のテスト"""
        mock_response = {
            "text": """
## 遵守状態
compliant

## 信頼度
0.95

## 説明
ファクトは条件を満たしています。
"""
        }
        self.mock_llm_processor.call_llm.return_value = mock_response

        conditions = [self.condition1]
        facts = [self.fact1]
        result = self.checker.check_pairs(conditions, facts)

        self.assertEqual(result.overall_status, ComplianceStatus.COMPLIANT)
        self.assertEqual(result.compliant_count, 1)
        self.assertEqual(result.non_compliant_count, 0)
        self.assertEqual(result.unrelated_count, 0)
        self.assertEqual(result.unknown_count, 0)
        self.assertEqual(result.total_count, 1)
        self.assertAlmostEqual(result.compliance_rate, 1.0)
        self.assertIn("すべてのペア", result.summary)
        self.assertEqual(len(result.pair_results), 1)
        self.assertEqual(result.pair_results[0].status, ComplianceStatus.COMPLIANT)
        self.assertAlmostEqual(result.pair_results[0].confidence_score, 0.95)
        self.assertEqual(
            result.pair_results[0].explanation, "ファクトは条件を満たしています。"
        )
        self.mock_llm_processor.call_llm.assert_called_once()

    def test_check_pairs_non_compliant(self):
        """ペアチェック（非適合）のテスト"""
        mock_response = {
            "text": """
## 遵守状態
non_compliant

## 信頼度
0.8

## 説明
ファクトは条件を満たしていません。
"""
        }
        self.mock_llm_processor.call_llm.return_value = mock_response

        conditions = [self.condition1]
        facts = [self.fact2]
        result = self.checker.check_pairs(conditions, facts)

        self.assertEqual(result.overall_status, ComplianceStatus.NON_COMPLIANT)
        self.assertEqual(result.compliant_count, 0)
        self.assertEqual(result.non_compliant_count, 1)
        self.assertEqual(result.unrelated_count, 0)
        self.assertEqual(result.unknown_count, 0)
        self.assertEqual(result.total_count, 1)
        self.assertAlmostEqual(result.compliance_rate, 0.0)
        self.assertIn("個のペアが非適合です", result.summary)
        self.assertEqual(len(result.pair_results), 1)
        self.assertEqual(result.pair_results[0].status, ComplianceStatus.NON_COMPLIANT)
        self.assertAlmostEqual(result.pair_results[0].confidence_score, 0.8)
        self.assertEqual(
            result.pair_results[0].explanation, "ファクトは条件を満たしていません。"
        )
        self.mock_llm_processor.call_llm.assert_called_once()

    def test_check_pairs_mixed(self):
        """ペアチェック（混合）のテスト"""
        # 複数のペアに対するモック応答を設定
        mock_responses = [
            {  # condition1 vs fact1 (compliant)
                "text": """
## 遵守状態
compliant

## 信頼度
0.95

## 説明
ファクトは条件を満たしています。
"""
            },
            {  # condition1 vs fact2 (non_compliant)
                "text": """
## 遵守状態
non_compliant

## 信頼度
0.8
## 説明
ファクトは条件を満たしていません。
"""
            },
        ]
        self.mock_llm_processor.call_llm.side_effect = mock_responses

        conditions = [self.condition1]
        facts = [self.fact1, self.fact2]
        result = self.checker.check_pairs(conditions, facts)

        self.assertEqual(result.overall_status, ComplianceStatus.NON_COMPLIANT)
        self.assertEqual(result.compliant_count, 1)
        self.assertEqual(result.non_compliant_count, 1)
        self.assertEqual(result.unrelated_count, 0)
        self.assertEqual(result.unknown_count, 0)
        self.assertEqual(result.total_count, 2)
        self.assertAlmostEqual(result.compliance_rate, 0.5)
        self.assertIn("個のペアが非適合です", result.summary)
        self.assertEqual(len(result.pair_results), 2)

        # 結果の順序は保証されないため、内容で検証
        compliant_result = next(
            r for r in result.pair_results if r.status == ComplianceStatus.COMPLIANT
        )
        non_compliant_result = next(
            r for r in result.pair_results if r.status == ComplianceStatus.NON_COMPLIANT
        )

        self.assertEqual(compliant_result.condition.text, self.condition1.text)
        self.assertEqual(compliant_result.fact.text, self.fact1.text)
        self.assertAlmostEqual(compliant_result.confidence_score, 0.95)
        self.assertEqual(
            compliant_result.explanation, "ファクトは条件を満たしています。"
        )

        self.assertEqual(non_compliant_result.condition.text, self.condition1.text)
        self.assertEqual(non_compliant_result.fact.text, self.fact2.text)
        self.assertAlmostEqual(non_compliant_result.confidence_score, 0.8)
        self.assertEqual(
            non_compliant_result.explanation, "ファクトは条件を満たしていません。"
        )

        self.assertEqual(self.mock_llm_processor.call_llm.call_count, 2)

    def test_check_pairs_unrelated(self):
        """ペアチェック（無関係）のテスト"""
        mock_response = {
            "text": """
## 遵守状態
unrelated

## 信頼度
0.7

## 説明
条件とファクトは無関係です。
"""
        }
        self.mock_llm_processor.call_llm.return_value = mock_response

        condition_unrelated = PairCheckItem(
            text="天気について",
            source="source.txt",
            item_type=PairCheckItemType.CONDITION,
        )
        fact_unrelated = PairCheckItem(
            text="今日の気温は25度です",
            source="target.txt",
            item_type=PairCheckItemType.FACT,
        )

        conditions = [condition_unrelated]
        facts = [fact_unrelated]
        result = self.checker.check_pairs(conditions, facts)

        self.assertEqual(result.overall_status, ComplianceStatus.UNRELATED)
        self.assertEqual(result.compliant_count, 0)
        self.assertEqual(result.non_compliant_count, 0)
        self.assertEqual(result.unrelated_count, 1)
        self.assertEqual(result.unknown_count, 0)
        self.assertEqual(result.total_count, 1)
        self.assertAlmostEqual(result.compliance_rate, 0.0)
        self.assertIn("すべてのペア（1個）が無関係です。", result.summary)
        self.assertEqual(len(result.pair_results), 1)
        self.assertEqual(result.pair_results[0].status, ComplianceStatus.UNRELATED)
        self.assertAlmostEqual(result.pair_results[0].confidence_score, 0.7)
        self.assertEqual(
            result.pair_results[0].explanation, "条件とファクトは無関係です。"
        )
        self.mock_llm_processor.call_llm.assert_called_once()

    def test_check_pairs_unknown(self):
        """ペアチェック（不明）のテスト"""
        mock_response = {
            "text": """
## 遵守状態
invalid_status # 不正なステータス

## 信頼度
invalid_confidence # 不正な信頼度

## 説明
解析できませんでした。
"""
        }
        self.mock_llm_processor.call_llm.return_value = mock_response

        conditions = [self.condition1]
        facts = [self.fact1]
        result = self.checker.check_pairs(conditions, facts)

        self.assertEqual(result.overall_status, ComplianceStatus.UNKNOWN)
        self.assertEqual(result.compliant_count, 0)
        self.assertEqual(result.non_compliant_count, 0)
        self.assertEqual(result.unrelated_count, 0)
        self.assertEqual(result.unknown_count, 1)
        self.assertEqual(result.total_count, 1)
        self.assertAlmostEqual(result.compliance_rate, 0.0)
        self.assertIn("判定不能なペアがあります", result.summary)
        self.assertEqual(len(result.pair_results), 1)
        self.assertEqual(result.pair_results[0].status, ComplianceStatus.UNKNOWN)
        self.assertAlmostEqual(
            result.pair_results[0].confidence_score, 0.0
        )  # 解析失敗時はデフォルト値
        self.assertEqual(
            result.pair_results[0].explanation, "解析できませんでした。"
        )  # 解析失敗時は抽出できた説明を使用
        self.mock_llm_processor.call_llm.assert_called_once()


if __name__ == "__main__":
    unittest.main()
