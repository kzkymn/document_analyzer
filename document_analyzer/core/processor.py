"""
抽象LLMプロセッサーモジュール。
テキスト処理からLLM回答生成までの基本フローを定義する。
"""

import abc
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel

from ..utils.logging import logger


class ComplianceStatus(str, Enum):
    """適合状態を表す列挙型"""
    COMPLIANT = "compliant"  # 適合している
    NON_COMPLIANT = "non_compliant"  # 適合していない
    UNRELATED = "unrelated"  # 無関係
    UNKNOWN = "unknown"  # 不明


class Evidence(BaseModel):
    """根拠を表すデータクラス"""
    text: str  # 根拠となるテキスト
    source: Optional[str] = None  # 出典（ソーステキストまたはファイル）
    relevance: Optional[float] = None  # 関連度（0.0〜1.0）


class Recommendation(BaseModel):
    """推奨事項を表すデータクラス"""
    text: str  # 推奨事項のテキスト
    priority: Optional[int] = None  # 優先度（1〜5、1が最高）


class AnalysisResult(BaseModel):
    """分析結果を表すデータクラス"""
    status: ComplianceStatus  # 適合状態
    confidence_score: float  # 信頼度スコア（0.0〜1.0）
    summary: str  # 要約
    evidence: List[Evidence]  # 根拠のリスト
    recommendations: List[Recommendation]  # 推奨事項のリスト
    raw_response: Optional[Dict[str, Any]] = None  # LLMからの生の応答


class LLMProcessor(abc.ABC):
    """抽象LLMプロセッサークラス"""
    
    def __init__(self):
        """初期化"""
        self.logger = logger
    
    def process(self, reference_text: str, file_path: Union[str, Path], config_path: Optional[str] = None) -> AnalysisResult:
        """
        参照テキストとファイルを処理し、分析結果を返す。
        
        Args:
            reference_text: 参照テキスト（ソーステキストなど）
            file_path: 分析対象ファイルのパス
            config_path: 設定ファイルのパス
            
        Returns:
            分析結果
        """
        self.logger.info(f"処理開始: {file_path}")
        
        # 参照テキストを前処理
        processed_reference = self.preprocess_reference_text(reference_text)
        self.logger.debug("参照テキストの前処理完了")
        
        # ファイルを前処理
        processed_file = self.preprocess_file(file_path)
        self.logger.debug("ファイルの前処理完了")
        
        # プロンプトを生成（設定ファイルのパスを渡す）
        prompt = self.generate_prompt(processed_reference, processed_file, config_path=config_path)
        self.logger.debug("プロンプト生成完了")
        
        # LLMを呼び出し
        raw_response = self.call_llm(prompt)
        self.logger.debug("LLM呼び出し完了")
        
        # 応答を解析
        result = self.parse_response(raw_response)
        self.logger.info(f"処理完了: {file_path}, 状態: {result.status.value}")
        
        return result
    
    @abc.abstractmethod
    def preprocess_reference_text(self, text: str) -> str:
        """
        参照テキストを前処理する。
        
        Args:
            text: 参照テキスト
            
        Returns:
            前処理されたテキスト
        """
        pass
    
    @abc.abstractmethod
    def preprocess_file(self, file_path: Union[str, Path]) -> str:
        """
        ファイルを前処理する。
        
        Args:
            file_path: ファイルパス
            
        Returns:
            前処理されたファイル内容
        """
        pass
    
    @abc.abstractmethod
    def generate_prompt(self, reference_text: str, file_content: str, config_path: Optional[str] = None) -> str:
        """
        プロンプトを生成する。
        
        Args:
            reference_text: 前処理された参照テキスト
            file_content: 前処理されたファイル内容
            config_path: 設定ファイルのパス
            
        Returns:
            生成されたプロンプト
        """
        pass
    
    @abc.abstractmethod
    def call_llm(self, prompt: str) -> Dict[str, Any]:
        """
        LLMを呼び出す。
        
        Args:
            prompt: プロンプト
            
        Returns:
            LLMからの応答
        """
        pass
    
    @abc.abstractmethod
    def parse_response(self, response: Dict[str, Any]) -> AnalysisResult:
        """
        LLMの応答を解析する。
        
        Args:
            response: LLMからの応答
            
        Returns:
            分析結果
        """
        pass