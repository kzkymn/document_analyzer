"""
レポート生成モジュール。
分析結果をMarkdownレポートに変換する。
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from ..utils.config import config
from ..utils.logging import logger
from .pair_check import PairCheckResult
from .processor import AnalysisResult, ComplianceStatus


class ReportGenerator:
    """レポート生成クラス"""

    def __init__(self):
        """初期化"""
        self.logger = logger
        self.config = config

    def generate_report(
        self, result: AnalysisResult, reference_path: str, target_path: str
    ) -> str:
        """
        分析結果からMarkdownレポートを生成する。

        Args:
            result: 分析結果
            reference_path: 参照テキスト（ソーステキストなど）のパス
            target_path: 分析対象ファイルのパス

        Returns:
            Markdownレポート
        """
        if result is None:
            self.logger.error("Result is None, cannot generate report.")
            return ""
        self.logger.info(f"Generating report for result: {result}")
        # 現在時刻
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ステータスに応じたアイコンとメッセージ
        status_icon, status_message = self._get_status_info(result.status)

        # レポートのヘッダー
        header = f"""# 文書分析レポート
        
**生成日時:** {now}
        
**参照テキスト:** {Path(reference_path).name}
**分析対象:** {Path(target_path).name}
        
## 分析結果サマリー
        
{status_icon} **遵守状態:** {status_message}
**信頼度:** {result.confidence_score:.2f}
        
{result.summary}
"""

        # 根拠セクション
        evidence_section = """
## 根拠

"""
        if result.evidence:
            for i, evidence in enumerate(result.evidence, 1):
                evidence_section += f"{i}. {evidence.text}\n"
        else:
            evidence_section += "根拠は提供されていません。\n"

        # 推奨事項セクション
        recommendations_section = """
## 推奨事項

"""
        if result.status == ComplianceStatus.NON_COMPLIANT and result.recommendations:
            for i, recommendation in enumerate(result.recommendations, 1):
                priority_str = (
                    f"（優先度: {recommendation.priority}）"
                    if recommendation.priority
                    else ""
                )
                recommendations_section += (
                    f"{i}. {recommendation.text} {priority_str}\n"
                )
        elif result.status == ComplianceStatus.COMPLIANT:
            recommendations_section += "対象文書はソーステキストの要件を満たしているため、推奨事項はありません。\n"
        elif result.status == ComplianceStatus.UNRELATED:
            recommendations_section += (
                "対象文書はソーステキストと無関係であるため、推奨事項はありません。\n"
            )
        else:
            recommendations_section += "推奨事項は提供されていません。\n"

        # 詳細情報セクション
        details_section = """
## 詳細情報

"""
        details_section += f"- **分析実施日時:** {now}\n"
        details_section += f"- **参照テキスト:** {reference_path}\n"
        details_section += f"- **分析対象:** {target_path}\n"

        # フッター
        footer = """
---
*このレポートは自動生成されたものであり、専門的なアドバイスを構成するものではありません。*
"""

        # レポート全体を組み立て
        report = (
            header
            + evidence_section
            + recommendations_section
            + details_section
            + footer
        )

        return report

    def generate_pair_check_report(
        self, result: PairCheckResult, source_path: str, target_path: str
    ) -> str:
        """
        ペアチェック結果からMarkdownレポートを生成する。

        Args:
            result: ペアチェック結果
            source_path: 参照テキスト（ソーステキストなど）のパス
            target_path: 分析対象ファイルのパス

        Returns:
            Markdownレポート
        """
        self.logger.info("ペアチェックレポート生成開始")

        # 現在時刻
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ステータスに応じたアイコンとメッセージ
        status_icon, status_message = self._get_status_info(result.overall_status)

        # レポートのヘッダー
        header = f"""# ペアチェックレポート

**生成日時:** {now}

**参照テキスト:** {Path(source_path).name}
**分析対象:** {Path(target_path).name}

## 分析結果サマリー

{status_icon} **遵守状態:** {status_message}
**適合率:** {result.compliance_rate:.1%}

**適合:** {result.compliant_count}個
**非適合:** {result.non_compliant_count}個
**無関係:** {result.unrelated_count}個
**不明:** {result.unknown_count}個
**合計:** {result.total_count}個

{result.summary}
"""

        # ペア結果セクション
        pairs_section = """
## ペア詳細結果

"""

        # 結果をステータス別にグループ化
        from .pair_check import PairCheckResult, PairResult  # ここでインポートが必要

        compliant_pairs = [
            p for p in result.pair_results if p.status == ComplianceStatus.COMPLIANT
        ]
        non_compliant_pairs = [
            p for p in result.pair_results if p.status == ComplianceStatus.NON_COMPLIANT
        ]
        unrelated_pairs = [
            p for p in result.pair_results if p.status == ComplianceStatus.UNRELATED
        ]
        unknown_pairs = [
            p for p in result.pair_results if p.status == ComplianceStatus.UNKNOWN
        ]

        # 非適合ペアを表示
        if non_compliant_pairs:
            pairs_section += """
### 非適合ペア

"""
            for i, pair in enumerate(non_compliant_pairs, 1):
                pairs_section += f"""
#### ペア {i}: ❌ 非適合 (信頼度: {pair.confidence_score:.2f})

**条件:** {pair.condition.text}

**ファクト:** {pair.fact.text}

**説明:** {pair.explanation}

---
"""

        # 適合ペアを表示
        if compliant_pairs:
            pairs_section += """
### 適合ペア

"""
            for i, pair in enumerate(compliant_pairs, 1):
                pairs_section += f"""
#### ペア {i}: ✅ 適合 (信頼度: {pair.confidence_score:.2f})

**条件:** {pair.condition.text}

**ファクト:** {pair.fact.text}

**説明:** {pair.explanation}

---
"""

        # 無関係ペアを表示
        if unrelated_pairs:
            pairs_section += """
### 無関係ペア

"""
            for i, pair in enumerate(unrelated_pairs, 1):
                pairs_section += f"""
#### ペア {i}: ⚠️ 無関係 (信頼度: {pair.confidence_score:.2f})

**条件:** {pair.condition.text}

**ファクト:** {pair.fact.text}

**説明:** {pair.explanation}

---
"""

        # 不明ペアを表示
        if unknown_pairs:
            pairs_section += """
### 不明ペア

"""
            for i, pair in enumerate(unknown_pairs, 1):
                pairs_section += f"""
#### ペア {i}: ❓ 不明 (信頼度: {pair.confidence_score:.2f})

**条件:** {pair.condition.text}

**ファクト:** {pair.fact.text}

**説明:** {pair.explanation}

---
"""

        # 詳細情報セクション
        details_section = """
## 詳細情報

"""
        details_section += f"- **分析実施日時:** {now}\n"
        details_section += f"- **参照テキスト:** {source_path}\n"
        details_section += f"- **分析対象:** {target_path}\n"
        details_section += f"- **抽出条件数:** {len({p.condition.text for p in result.pair_results})}\n"
        details_section += (
            f"- **抽出ファクト数:** {len({p.fact.text for p in result.pair_results})}\n"
        )

        # フッター
        footer = """
---
*このレポートは自動生成されたものであり、専門的なアドバイスを構成するものではありません。*
"""

        # レポート全体を組み立て
        report = header + pairs_section + details_section + footer

        self.logger.info("ペアチェックレポート生成完了")
        return report

    def save_report(
        self, report: str, output_path: Optional[Union[str, Path]] = None
    ) -> Path:
        """
        レポートをファイルに保存する。

        Args:
            report: レポート内容
            output_path: 出力先パス。指定されない場合は自動生成。

        Returns:
            保存先のパス
        """
        if output_path is None:
            # 出力先が指定されていない場合は、現在時刻を使用してファイル名を生成
            now = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"analysis_report_{now}.md"

        path = Path(output_path)

        # 親ディレクトリが存在しない場合は作成
        path.parent.mkdir(parents=True, exist_ok=True)

        # レポートを保存
        with open(path, "w", encoding="utf-8") as f:
            f.write(report)

        self.logger.info(f"レポートを保存しました: {path}")
        return path

    def _get_status_info(self, status: ComplianceStatus) -> tuple:
        """
        ステータスに応じたアイコンとメッセージを取得する。

        Args:
            status: 遵守状態

        Returns:
            (アイコン, メッセージ)のタプル
        """
        if status == ComplianceStatus.COMPLIANT:
            return "✅", "遵守"
        elif status == ComplianceStatus.NON_COMPLIANT:
            return "❌", "違反"
        elif status == ComplianceStatus.UNRELATED:
            return "⚠️", "無関係"
        else:
            return "❓", "不明"
