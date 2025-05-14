"""
LLMモジュール。
様々なLLMプロセッサーを提供する。
"""

from .gemini import GeminiProcessor
from .openai import OpenAIProcessor

# 利用可能なプロセッサーをエクスポート
__all__ = ["GeminiProcessor", "OpenAIProcessor"]
