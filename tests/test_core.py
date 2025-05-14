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
        # プロンプト取得をモックし、単純なテンプレートを返す
        self.get_prompt_patcher = mock.patch(
            "document_analyzer.utils.config.config.get_prompt_content",
            return_value="テキスト:{text}\n構造:{structure_summary}",
        )
        self.get_prompt_patcher.start()

        self.extractor = TextExtractor(self.mock_llm_processor)

    def tearDown(self):
        """テスト後のクリーンアップ"""
        # get_prompt_patcher を停止
        self.get_prompt_patcher.stop()

    def test_extract_conditions(self):
        """チェック条件抽出のテスト"""
        test_text = """
        以下の要件を満たす必要があります。
        - レポートは週次で提出すること
        - プロジェクトの進捗状況を詳細に記載すること
        事実：進捗は順調です。
        """
        mock_response = {
            "text": "- レポートは週次で提出すること\n- プロジェクトの進捗状況を詳細に記載すること",
            # プロンプトテンプレートが期待するキーを追加
            "structure_summary": "テスト構造の要約",
        }
        self.mock_llm_processor.call_llm.return_value = mock_response

        conditions = self.extractor.extract_conditions(test_text, "test_source.txt")

        self.assertEqual(len(conditions), 2)
        self.assertEqual(conditions[0].text, "レポートは週次で提出すること")
        self.assertEqual(conditions[0].source, "test_source.txt")
        self.assertEqual(conditions[0].item_type, PairCheckItemType.CONDITION)
        self.assertEqual(
            conditions[1].text, "プロジェクトの進捗状況を詳細に記載すること"
        )
        self.assertEqual(conditions[1].source, "test_source.txt")
        self.assertEqual(conditions[1].item_type, PairCheckItemType.CONDITION)
        self.mock_llm_processor.call_llm.assert_called_once()

    def test_extract_facts(self):
        """ファクト抽出のテスト"""
        test_text = """
        今週の進捗は以下の通りです。
        - 設計フェーズが完了しました
        - 実装フェーズを開始しました
        要件：設計を完了すること。
        """
        mock_response = {
            "text": "- 設計フェーズが完了しました\n- 実装フェーズを開始しました",
            # プロンプトテンプレートが期待するキーを追加
            "structure_summary": "テスト構造の要約",
        }
        self.mock_llm_processor.call_llm.return_value = mock_response

        facts = self.extractor.extract_facts(test_text, "test_target.txt")

        self.assertEqual(len(facts), 2)
        self.assertEqual(facts[0].text, "設計フェーズが完了しました")
        self.assertEqual(facts[0].source, "test_target.txt")
        self.assertEqual(facts[0].item_type, PairCheckItemType.FACT)
        self.assertEqual(facts[1].text, "実装フェーズを開始しました")
        self.assertEqual(facts[1].source, "test_target.txt")
        self.assertEqual(facts[1].item_type, PairCheckItemType.FACT)
        self.mock_llm_processor.call_llm.assert_called_once()


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
