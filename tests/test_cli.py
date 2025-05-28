"""
CLIモジュールのテスト
"""

from pathlib import Path
from unittest import mock

import yaml
from click.testing import CliRunner

from document_analyzer.cli import cli
from document_analyzer.core.pair_check import (
    PairCheckItem,
    PairCheckItemType,
    PairCheckResult,
    PairResult,
)
from document_analyzer.core.processor import (
    AnalysisResult,
    ComplianceStatus,
    Evidence,
    Recommendation,
)


def test_check_command_with_config():
    """設定ファイルを指定してcheckコマンドを実行できることをテスト"""
    runner = CliRunner()

    # 分離されたファイルシステムを使用
    with runner.isolated_filesystem():
        # 設定ファイルを作成
        config_path = "test_config.yaml"
        source_path = "test_source.txt"
        target_path = "test_target.txt"

        # 設定ファイルの内容を書き込む
        config_data = {
            "prompt": {
                "template_path": "test_prompt.txt",
                "description": "テスト用設定",
            },
            "logging": {"level": "INFO"},
            "llm": {
                "default": "gemini",
                "models": {"gemini": {"model_name": "gemini-2.0-flash"}},
            },
            "output": {"format": "markdown"},
            # CLIコマンドが参照するプロンプトファイルのパスを追加
            "prompts": {
                "should_extract": "config/prompts/should_extract_prompt.txt",
                "condition_extraction": "config/prompts/condition_extraction_prompt.txt",
                "fact_extraction": "config/prompts/fact_extraction_prompt.txt",
            },
        }
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

        # test_prompt.txt を作成
        with open("test_prompt.txt", "w", encoding="utf-8") as f:
            f.write(
                "これはテスト用のプロンプトテンプレートです。\nテキスト: {reference_text}\nファイル内容: {file_content}"
            )

        # config/prompts/should_extract_prompt.txt を作成
        # ディレクトリも作成する必要がある
        Path("config/prompts").mkdir(parents=True, exist_ok=True)
        with open(
            "config/prompts/should_extract_prompt.txt", "w", encoding="utf-8"
        ) as f:
            f.write(
                "以下のテキストから条件やファクトを抽出するべきか判断してください。\nファイルパス: {file_path}\nファイルサイズ: {file_size}\nファイル冒頭: {file_head}\nソースコンテキスト: {source_context}"
            )

        # 条件抽出用プロンプトファイルを作成
        with open(
            "config/prompts/condition_extraction_prompt.txt", "w", encoding="utf-8"
        ) as f:
            f.write("テキスト: {text}\n構造情報: {structure_summary}")

        # ファクト抽出用プロンプトファイルを作成
        with open(
            "config/prompts/fact_extraction_prompt.txt", "w", encoding="utf-8"
        ) as f:
            f.write("テキスト: {text}\n構造情報: {structure_summary}")

        # ソーステキストファイルを作成
        with open(source_path, "w", encoding="utf-8") as f:
            f.write("テスト用のソーステキスト")

        # ターゲットファイルを作成
        with open(target_path, "w", encoding="utf-8") as f:
            f.write("テスト用のターゲットファイル")

        # TextComparisonAnalyzer とその依存関係をモック
        with mock.patch(
            "document_analyzer.cli.commands.check.TextComparisonAnalyzer"
        ) as MockAnalyzer, mock.patch(
            "document_analyzer.core.extractor.TextExtractor.extract_conditions"
        ) as mock_extract_conditions, mock.patch(
            "document_analyzer.core.extractor.TextExtractor.extract_facts"
        ) as mock_extract_facts, mock.patch(
            "document_analyzer.cli.commands.check.run_pair_check"
        ) as mock_run_pair_check:
            # MockAnalyzerのインスタンスとそのprocessor属性をモック
            mock_analyzer_instance = MockAnalyzer.return_value
            mock_analyzer_instance.processor = mock.Mock()
            mock_analyzer_instance.processor.should_extract_items.return_value = (
                True,
                "mocked",
            )

            # extract_conditions と extract_facts のモック戻り値を設定
            conditions = [
                PairCheckItem(
                    text="条件1",
                    source="test_source.txt",
                    item_type=PairCheckItemType.CONDITION,
                )
            ]
            mock_extract_conditions.return_value = conditions

            facts = [
                PairCheckItem(
                    text="ファクト1",
                    source="test_target.txt",
                    item_type=PairCheckItemType.FACT,
                )
            ]
            mock_extract_facts.return_value = facts

            # run_pair_check のモック戻り値を設定
            mock_run_pair_check.return_value = PairCheckResult(
                overall_status=ComplianceStatus.COMPLIANT,
                pair_results=[],
                compliant_count=1,
                non_compliant_count=0,
                unrelated_count=0,
                unknown_count=0,
                total_count=1,
                compliance_rate=1.0,
                summary="テスト用のペアチェック要約",
            )

            # CLIコマンドを実行
            result = runner.invoke(
                cli,
                [
                    "check",
                    "--source-file",
                    source_path,
                    "--target-file",
                    target_path,
                    "--config",
                    config_path,
                    "--yes",  # ユーザー確認をスキップ
                ],
            )

            # 結果を検証
            assert result.exit_code == 0
            # should_extract_items が 2 回呼ばれることを確認
            assert mock_analyzer_instance.processor.should_extract_items.call_count == 2
            # extract_conditions と extract_facts がそれぞれ1回ずつ呼ばれることを確認
            mock_extract_conditions.assert_called_once()
            mock_extract_facts.assert_called_once()
            mock_run_pair_check.assert_called_once_with(
                mock_analyzer_instance,
                conditions,
                facts,
                source_path,
                target_path,
                None,  # output が None であることを期待
            )


def test_check_command_pair_check_logic():
    """新しいペアチェックの自律判断ロジックをテスト"""
    runner = CliRunner()

    # 分離されたファイルシステムを使用
    with runner.isolated_filesystem():
        # 設定ファイルを作成
        config_path = "test_config.yaml"
        source_path = "test_source.txt"
        target_path = "test_target.txt"
        output = "test_output.md"  # output変数を定義

        # 設定ファイルの内容を書き込む
        config_data = {
            "prompt": {
                "template_path": "test_prompt.txt",
                "description": "テスト用設定",
            },
            "logging": {"level": "INFO"},
            "llm": {
                "default": "gemini",
                "models": {"gemini": {"model_name": "gemini-2.0-flash"}},
            },
            "output": {"format": "markdown"},
        }
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

        # ソーステキストファイルを作成
        with open(source_path, "w", encoding="utf-8") as f:
            f.write("テスト用のソーステキスト")

        # ターゲットファイルを作成
        with open(target_path, "w", encoding="utf-8") as f:
            f.write("テスト用のターゲットファイル")

        # TextComparisonAnalyzerと関連メソッドをモック
        with mock.patch(
            "document_analyzer.cli.commands.check.TextComparisonAnalyzer"
        ) as MockAnalyzer, mock.patch(
            "document_analyzer.core.extractor.TextExtractor.extract_conditions"
        ) as mock_extract_conditions, mock.patch(
            "document_analyzer.core.extractor.TextExtractor.extract_facts"
        ) as mock_extract_facts, mock.patch(
            "document_analyzer.cli.commands.check.run_pair_check"
        ) as mock_run_pair_check, mock.patch(
            "document_analyzer.core.extractor.ResponseParser._parse_extraction_response"
        ) as mock_parse_extraction_response:  # ResponseParserをモック化

            # MockAnalyzerのインスタンスとそのprocessor属性、およびprocessorのメソッドをモック
            mock_analyzer_instance = MockAnalyzer.return_value
            mock_analyzer_instance.processor = mock.Mock()
            # should_extract_items は (bool, reason) のタプルを返す実装を模倣
            mock_analyzer_instance.processor.should_extract_items.side_effect = (
                lambda *args, **kwargs: (True, "mocked")
            )

            # extract_conditions/factsのモック戻り値を設定
            conditions = [
                PairCheckItem(
                    text="条件1",
                    source="test_source.txt",
                    item_type=PairCheckItemType.CONDITION,
                )
            ]
            mock_extract_conditions.return_value = conditions

            facts = [
                PairCheckItem(
                    text="ファクト1",
                    source="test_target.txt",
                    item_type=PairCheckItemType.FACT,
                )
            ]
            mock_extract_facts.return_value = facts

            # _parse_extraction_response のモック戻り値を設定
            mock_parse_extraction_response.return_value = [
                {"text": "条件1", "id": 1},
                {"text": "条件2", "id": 2},
            ]

            # run_pair_checkのモック戻り値を設定
            mock_run_pair_check.return_value = PairCheckResult(
                overall_status=ComplianceStatus.COMPLIANT,
                pair_results=[
                    PairResult(
                        condition=PairCheckItem(
                            text="条件1",
                            source="test_source.txt",
                            item_type=PairCheckItemType.CONDITION,
                        ),
                        fact=PairCheckItem(
                            text="ファクト1",
                            source="test_target.txt",
                            item_type=PairCheckItemType.FACT,
                        ),
                        status=ComplianceStatus.COMPLIANT,
                        confidence_score=0.9,
                        explanation="説明1",
                    )
                ],
                compliant_count=1,
                non_compliant_count=0,
                unrelated_count=0,
                unknown_count=0,
                total_count=1,
                compliance_rate=1.0,
                summary="テスト用のペアチェック要約",
            )

            # CLIコマンドを実行（--yesオプションを追加してユーザー確認をスキップ）
            result = runner.invoke(
                cli,
                [
                    "check",
                    "--source-file",
                    source_path,
                    "--target-file",
                    target_path,
                    "--config",
                    config_path,
                    "--output",  # --output オプションを追加
                    output,  # output変数を渡す
                    "--yes",
                ],
            )

            # 結果を検証
            assert result.exit_code == 0
            # 条件・ファクトで should_extract_items が 2 回呼ばれる
            assert mock_analyzer_instance.processor.should_extract_items.call_count == 2
            mock_extract_conditions.assert_called_once()
            mock_extract_facts.assert_called_once()
            mock_run_pair_check.assert_called_once_with(
                mock_analyzer_instance,
                conditions,
                facts,
                source_path,
                target_path,
                output,  # output
            )


def test_check_command_without_config():
    """設定ファイルを指定しない場合にエラーが発生することをテスト"""
    runner = CliRunner()

    # 分離されたファイルシステムを使用
    with runner.isolated_filesystem():
        # ソーステキストファイルを作成
        source_path = "test_source.txt"
        target_path = "test_target.txt"

        with open(source_path, "w", encoding="utf-8") as f:
            f.write("テスト用のソーステキスト")

        with open(target_path, "w", encoding="utf-8") as f:
            f.write("テスト用のターゲットファイル")

        # test_check_command_without_configでもモックを使用
        with mock.patch(
            "document_analyzer.core.analyzer.TextComparisonAnalyzer.analyze"
        ) as mock_analyze:
            mock_analyze.return_value = AnalysisResult(
                status=ComplianceStatus.COMPLIANT,
                confidence_score=0.95,
                summary="テスト用の要約",
                evidence=[Evidence(text="テスト用の根拠", source="test_source.txt")],
                recommendations=[],
                raw_response={"response": "テスト用のレスポンス"},
            )

        # CLIコマンドを実行（設定ファイルなし）
        result = runner.invoke(
            cli, ["check", "--source-file", source_path, "--target-file", target_path]
        )

        # 結果を検証
        assert result.exit_code != 0
        assert "Missing option" in result.output
        assert "--config" in result.output
