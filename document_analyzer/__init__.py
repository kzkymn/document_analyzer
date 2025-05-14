"""
文書分析ツール

2つのテキスト（または文書）を比較し、それらの関連性や適合性を分析する生成AIベースのアプリケーションです。
法令遵守チェックなど様々な用途に活用できます。
"""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .core.analyzer import TextComparisonAnalyzer
from .core.processor import AnalysisResult, ComplianceStatus, Evidence, Recommendation
from .core.report import ReportGenerator

__all__ = [
    "TextComparisonAnalyzer",
    "AnalysisResult",
    "ComplianceStatus",
    "Evidence",
    "Recommendation",
    "ReportGenerator",
]