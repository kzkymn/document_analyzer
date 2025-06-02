"""
ペアチェックモジュール。
条件とファクトのペアチェックに関連するクラスとロジックを提供する。
"""

from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import BaseModel

from .processor import ComplianceStatus


class PairCheckItemType(str, Enum):
    """ペアチェック項目の種類を表す列挙型"""

    CONDITION = "condition"  # チェック条件
    FACT = "fact"  # ファクト
    CHAPTER = "chapter"  # 章
    SECTION = "section"  # 節
    SUBSECTION = "subsection"  # 項


class PairCheckItem(BaseModel):
    """ペアチェック項目を表すデータクラス"""

    text: str  # テキスト
    source: Optional[str] = None  # 出典（ファイルパスなど）
    item_type: PairCheckItemType  # 項目の種類
    parent_id: Optional[int] = None  # 親項目のID（階層構造を表現するため）
    id: Optional[int] = None  # 項目のID（階層構造を表現するため）
    children: Optional[List["PairCheckItem"]] = None  # 子項目のリスト
    condition_ids: Optional[List[int]] = (
        None  # 関連する条件のIDリスト (ファクトの場合に設定)
    )


class PairResult(BaseModel):
    """ペアチェック結果を表すデータクラス"""

    condition: PairCheckItem  # チェック条件
    fact: PairCheckItem  # ファクト
    status: ComplianceStatus  # 適合状態
    confidence_score: float  # 信頼度スコア（0.0〜1.0）
    explanation: str  # 説明


class PairCheckResult(BaseModel):
    """ペアチェック全体の結果を表すデータクラス"""

    overall_status: ComplianceStatus  # 全体の適合状態
    pair_results: List[PairResult]  # ペアごとの結果リスト
    compliant_count: int  # 適合数
    non_compliant_count: int  # 非適合数
    unrelated_count: int  # 無関係数
    unknown_count: int  # 不明数
    total_count: int  # 合計数
    compliance_rate: float  # 適合率（0.0〜1.0）
    summary: str  # 要約
