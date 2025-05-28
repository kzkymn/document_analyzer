"""
Gemini LLMプロセッサーモジュール。
Google Gemini APIを使用したLLMプロセッサーの実装。
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import google.generativeai as genai
from pydantic import ValidationError

from ..core.processor import AnalysisResult, ComplianceStatus, Evidence, Recommendation
from ..utils.config import config
from .base import BaseLLMProcessor


class GeminiProcessor(BaseLLMProcessor):
    """Gemini LLMプロセッサークラス"""

    def __init__(self, model_config: Optional[Dict[str, Any]] = None):
        """
        初期化

        Args:
            model_config: モデル設定。指定されない場合は設定ファイルから取得。
        """
        super().__init__(model_config)

        # Gemini APIキーを設定
        api_key = config.get_gemini_api_key()
        genai.configure(api_key=api_key)

        # モデル設定を取得
        if not self.model_config:
            self.model_config = config.get_llm_config("gemini")

        # モデル名を取得
        self.model_name = self.model_config.get("model_name", "gemini-2.0-flash")

        # モデルを取得
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config={
                "temperature": self.model_config.get("temperature", 0.2),
                "max_output_tokens": self.model_config.get("max_output_tokens", 2048),
                "top_p": self.model_config.get("top_p", 0.95),
                "top_k": self.model_config.get("top_k", 40),
            },
        )

        self.logger.info(f"Geminiプロセッサーを初期化しました: {self.model_name}")

        # 利用可能なモデルをリストアップ（デバッグ用）
        print("利用可能なGeminiモデル:")
        for m in genai.list_models():
            if "generateContent" in m.supported_generation_methods:
                print(f"- {m.name}")

    def preprocess_file(self, file_path: Union[str, Path]) -> str:
        """
        ファイルを前処理する。
        Geminiの場合、テキストファイルはそのまま読み込み、
        その他のファイル形式は将来的に対応予定。

        Args:
            file_path: ファイルパス

        Returns:
            前処理されたファイル内容
        """
        # 基本的なテキストファイル処理を使用
        return super().preprocess_file(file_path)

    def should_extract_items(
        self,
        file_path: Union[str, Path],
        file_size: int,
        file_head: str,
        source_context: Optional[str] = None,
    ) -> tuple[bool, str]:
        """
        ファイルの内容から条件またはファクトの抽出が必要か判断する。
        Geminiモデルを使用して判断を行う。

        Args:
            file_path: ファイルパス
            file_size: ファイルサイズ (バイト)
            file_head: ファイル内容の冒頭部分
            source_context: ターゲットファイルの場合、ソースファイルの内容または抽出された条件

        Returns:
            (抽出要否, 判断根拠) のタプル。抽出が必要な場合はTrue、そうでない場合はFalse
        """
        self.logger.debug(f"Geminiに抽出要否を問い合わせます: {file_path}")

        # 親クラスのメソッドを呼び出して結果を取得
        need_extract, reason = super().should_extract_items(
            file_path, file_size, file_head, source_context
        )

        # ログメッセージをGemini用にカスタマイズ
        self.logger.debug(
            f"Geminiの判断: {file_path} から抽出{'が必要' if need_extract else 'は不要'}です。根拠: {reason}"
        )

        return need_extract, reason

    def call_llm(self, prompt: str) -> Dict[str, Any]:
        """
        Gemini APIを呼び出す。

        Args:
            prompt: プロンプト

        Returns:
            Gemini APIからの応答
        """
        self.logger.debug(f"Gemini APIを呼び出します: {self.model_name}")

        try:
            response = self.model.generate_content(prompt)

            # 応答を辞書形式に変換
            result = {
                "text": response.text,
                "raw_response": response,
            }

            return result

        except Exception as e:
            self.logger.error(f"Gemini API呼び出し中にエラーが発生しました: {str(e)}")
            raise

    def parse_response(self, response: Dict[str, Any]) -> AnalysisResult:
        """
        Gemini APIの応答を解析する。

        Args:
            response: Gemini APIからの応答

        Returns:
            分析結果
        """
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

        # 要約を抽出
        summary_match = re.search(
            r"## 要約\s*\n\s*(.+?)(?=\n\s*##|\Z)", text, re.DOTALL
        )
        summary = summary_match.group(1).strip() if summary_match else ""

        # 根拠を抽出
        evidence_list = []
        evidence_section_match = re.search(
            r"## 根拠\s*\n(.*?)(?=\n\s*##|\Z)", text, re.DOTALL
        )
        if evidence_section_match:
            evidence_section = evidence_section_match.group(1)
            evidence_items = re.findall(
                r"-\s*(.+?)(?=\n\s*-|\Z)", evidence_section, re.DOTALL
            )
            for item in evidence_items:
                evidence_list.append(Evidence(text=item.strip()))

        # 推奨事項を抽出
        recommendations_list = []
        recommendations_section_match = re.search(
            r"## 推奨事項\s*\n(.*?)(?=\n\s*##|\Z)", text, re.DOTALL
        )
        if recommendations_section_match:
            recommendations_section = recommendations_section_match.group(1)
            recommendation_items = re.findall(
                r"-\s*(.+?)(?=\n\s*-|\Z)", recommendations_section, re.DOTALL
            )
            for item in recommendation_items:
                recommendations_list.append(Recommendation(text=item.strip()))

        # 分析結果を作成
        try:
            result = AnalysisResult(
                status=status,
                confidence_score=confidence_score,
                summary=summary,
                evidence=evidence_list,
                recommendations=recommendations_list,
                raw_response={"text": text},
            )
            return result

        except ValidationError as e:
            self.logger.error(f"分析結果の検証中にエラーが発生しました: {str(e)}")
            # 最低限の情報で結果を作成
            return AnalysisResult(
                status=ComplianceStatus.UNKNOWN,
                confidence_score=0.0,
                summary="応答の解析中にエラーが発生しました",
                evidence=[],
                recommendations=[],
            )

    def call_critic_llm(self, prompt: str) -> Dict[str, Any]:
        """
        Critic LLMとしてGemini APIを呼び出す。
        通常のLLM呼び出しと同じモデルを使用するが、必要に応じて異なるモデルを設定することも可能。

        Args:
            prompt: プロンプト

        Returns:
            Gemini APIからの応答
        """
        self.logger.debug(
            f"Critic LLMとしてGemini APIを呼び出します: {self.model_name}"
        )
        try:
            response = self.model.generate_content(prompt)
            result = {
                "text": response.text,
                "raw_response": response,
            }
            return result
        except Exception as e:
            self.logger.error(
                f"Critic LLM (Gemini) 呼び出し中にエラーが発生しました: {str(e)}"
            )
        raise
