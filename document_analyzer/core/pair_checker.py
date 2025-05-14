"""
ペアチェッカーモジュール。
条件とファクトのペアをチェックするクラスを提供する。
"""

from typing import List, Optional, Tuple

from ..llm.base import BaseLLMProcessor
from .pair_check import PairCheckItem, PairCheckResult, PairResult
from .processor import ComplianceStatus


class PairChecker:
    """ペアチェッカークラス"""

    def __init__(self, llm_processor: BaseLLMProcessor):
        """
        初期化

        Args:
            llm_processor: LLMプロセッサー
        """
        self.llm_processor = llm_processor
        self.logger = llm_processor.logger

    def check_pairs(
        self, conditions: List[PairCheckItem], facts: List[PairCheckItem]
    ) -> PairCheckResult:
        """
        条件とファクトのペアをチェックする。

        Args:
            conditions: チェック条件のリスト
            facts: ファクトのリスト

        Returns:
            ペアチェック結果
        """
        self.logger.info(
            f"ペアチェックを開始します: {len(conditions)}個の条件 x {len(facts)}個のファクト"
        )

        # 全ての組み合わせをチェック
        pair_results = []
        for condition in conditions:
            for fact in facts:
                self.logger.debug(
                    f"ペアをチェックします: {condition.text[:30]}... と {fact.text[:30]}..."
                )
                pair_result = self._check_pair(condition, fact)
                pair_results.append(pair_result)

        # 結果を集計
        compliant_count = sum(
            1 for r in pair_results if r.status == ComplianceStatus.COMPLIANT
        )
        non_compliant_count = sum(
            1 for r in pair_results if r.status == ComplianceStatus.NON_COMPLIANT
        )
        unrelated_count = sum(
            1 for r in pair_results if r.status == ComplianceStatus.UNRELATED
        )
        unknown_count = sum(
            1 for r in pair_results if r.status == ComplianceStatus.UNKNOWN
        )
        total_count = len(pair_results)
        compliance_rate = compliant_count / total_count if total_count > 0 else 0.0

        # 全体の状態を判定
        overall_status = self._determine_overall_status(
            compliant_count, non_compliant_count, unrelated_count, unknown_count
        )

        # 要約を生成
        summary = self._generate_summary(
            overall_status,
            compliant_count,
            non_compliant_count,
            unrelated_count,
            unknown_count,
            total_count,
        )

        # 結果を作成
        result = PairCheckResult(
            overall_status=overall_status,
            pair_results=pair_results,
            compliant_count=compliant_count,
            non_compliant_count=non_compliant_count,
            unrelated_count=unrelated_count,
            unknown_count=unknown_count,
            total_count=total_count,
            compliance_rate=compliance_rate,
            summary=summary,
        )

        self.logger.info(f"ペアチェックが完了しました: {summary}")
        return result

    def _check_pair(self, condition: PairCheckItem, fact: PairCheckItem) -> PairResult:
        """
        条件とファクトのペアをチェックする。

        Args:
            condition: チェック条件
            fact: ファクト

        Returns:
            ペアチェック結果
        """
        # LLMを使用してペアをチェック
        prompt = self._get_pair_check_prompt(condition.text, fact.text)
        self.logger.info(f"Calling LLM for pair check: {condition.text} vs {fact.text}")
        response = self.llm_processor.call_llm(prompt)
        status, confidence_score, explanation = self._parse_pair_check_response(
            response
        )

        # 結果を作成
        result = PairResult(
            condition=condition,
            fact=fact,
            status=status,
            confidence_score=confidence_score,
            explanation=explanation,
        )

        return result

    def _get_pair_check_prompt(self, condition: str, fact: str) -> str:
        """
        ペアチェック用のプロンプトを取得する。

        Args:
            condition: チェック条件
            fact: ファクト

        Returns:
            プロンプト
        """
        from document_analyzer.utils.config import config

        prompt_template = config.get_prompt_content("pair_check")
        prompt = prompt_template.format(condition=condition, fact=fact)
        return prompt

    def _parse_pair_check_response(
        self, response: dict
    ) -> Tuple[ComplianceStatus, float, str]:
        """
        ペアチェック応答を解析する。

        Args:
            response: LLMからの応答

        Returns:
            (適合状態, 信頼度, 説明)のタプル
        """
        import re

        text = response.get("text", "")

        # 適合状態を抽出
        status_match = re.search(
            r"## (遵守状態|適合状態)\s*\n\s*(compliant|non_compliant|unrelated)",
            text,
            re.IGNORECASE,
        )
        status_str = status_match.group(2).lower() if status_match else "unknown"
        status = ComplianceStatus(status_str)

        # 信頼度を抽出
        confidence_match = re.search(r"## 信頼度\s*\n\s*([0-9]*\.?[0-9]+)", text)
        confidence_score = float(confidence_match.group(1)) if confidence_match else 0.0

        # 説明を抽出
        explanation_match = re.search(
            r"## 説明\s*\n\s*(.+?)(?=\n\s*##|\Z)", text, re.DOTALL
        )
        explanation = explanation_match.group(1).strip() if explanation_match else ""

        return status, confidence_score, explanation

    def _determine_overall_status(
        self,
        compliant_count: int,
        non_compliant_count: int,
        unrelated_count: int,
        unknown_count: int,
    ) -> ComplianceStatus:
        """
        全体の状態を判定する。

        Args:
            compliant_count: 適合数
            non_compliant_count: 非適合数
            unrelated_count: 無関係数
            unknown_count: 不明数

        Returns:
            全体の適合状態
        """
        # 一つでも非適合があれば非適合
        if non_compliant_count > 0:
            return ComplianceStatus.NON_COMPLIANT

        # 非適合がなく、適合が1つ以上あれば適合
        if compliant_count > 0:
            return ComplianceStatus.COMPLIANT

        # 適合も非適合もなく、すべてが無関係なら無関係
        if (
            unrelated_count > 0
            and compliant_count == 0
            and non_compliant_count == 0
            and unknown_count == 0
        ):
            return ComplianceStatus.UNRELATED

        # それ以外は不明
        return ComplianceStatus.UNKNOWN

    def _generate_summary(
        self,
        overall_status: ComplianceStatus,
        compliant_count: int,
        non_compliant_count: int,
        unrelated_count: int,
        unknown_count: int,
        total_count: int,
    ) -> str:
        """
        要約を生成する。

        Args:
            overall_status: 全体の適合状態
            compliant_count: 適合数
            non_compliant_count: 非適合数
            unrelated_count: 無関係数
            unknown_count: 不明数
            total_count: 合計数

        Returns:
            要約
        """
        compliance_rate = compliant_count / total_count if total_count > 0 else 0.0

        if overall_status == ComplianceStatus.COMPLIANT:
            return f"すべてのペア（{total_count}個）が適合しています。適合率: 100%"
        elif overall_status == ComplianceStatus.NON_COMPLIANT:
            return f"{non_compliant_count}個のペアが非適合です。適合率: {compliance_rate:.1%}"
        elif overall_status == ComplianceStatus.UNRELATED:
            return f"すべてのペア（{total_count}個）が無関係です。"
        else:
            return f"判定不能なペアがあります。適合: {compliant_count}個、非適合: {non_compliant_count}個、無関係: {unrelated_count}個、不明: {unknown_count}個"
