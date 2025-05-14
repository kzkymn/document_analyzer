"""
設定管理モジュール。
環境変数、設定ファイル、コマンドライン引数から設定を読み込む。
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from dotenv import load_dotenv

# .envファイルを読み込む
load_dotenv()


class Config:
    """設定管理クラス"""

    def __init__(self, config_path: Optional[str] = None):
        """
        設定を初期化する。

        Args:
            config_path: 設定ファイルのパス。指定されない場合はデフォルトのパスを使用。
        """
        self.config_dir = Path(__file__).parent.parent.parent / "config"
        self.default_config_path = self.config_dir / "default.yaml"
        self.config_path = Path(config_path) if config_path else None
        self.config = self._load_config()

    def _deep_merge_dicts(self, base_dict: Dict, merge_dict: Dict) -> Dict:
        """
        二つの辞書を再帰的にマージする。

        Args:
            base_dict: ベースとなる辞書
            merge_dict: マージする辞書

        Returns:
            マージされた新しい辞書
        """
        merged = base_dict.copy()
        for k, v in merge_dict.items():
            if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
                merged[k] = self._deep_merge_dicts(merged[k], v)
            else:
                merged[k] = v
        return merged

    def _load_config(self) -> Dict[str, Any]:
        """
        設定ファイルを読み込む。

        Returns:
            設定辞書
        """
        # まずデフォルト設定を読み込む
        if not self.default_config_path.exists():
            raise FileNotFoundError(
                f"デフォルト設定ファイルが見つかりません: {self.default_config_path}"
            )

        with open(self.default_config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # --configで指定された設定ファイルがあれば読み込み、デフォルト設定にマージする
        if self.config_path and self.config_path != self.default_config_path:
            if not self.config_path.exists():
                raise FileNotFoundError(
                    f"設定ファイルが見つかりません: {self.config_path}"
                )

            with open(self.config_path, "r", encoding="utf-8") as f:
                user_config = yaml.safe_load(f)

            if user_config:
                config = self._deep_merge_dicts(config, user_config)

        # 環境変数で設定を上書き
        self._override_from_env(config)

        return config

    def _override_from_env(self, config: Dict[str, Any]) -> None:
        """
        環境変数で設定を上書きする。

        Args:
            config: 設定辞書
        """
        # LLM設定
        if os.getenv("GEMINI_API_KEY"):
            # APIキーは設定ファイルには保存せず、環境変数から取得する
            pass

        # Geminiモデル名の設定
        if os.getenv("GEMINI_MODEL_NAME"):
            if "llm" not in config:
                config["llm"] = {}
            if "models" not in config["llm"]:
                config["llm"]["models"] = {}
            if "gemini" not in config["llm"]["models"]:
                config["llm"]["models"]["gemini"] = {}

            config["llm"]["models"]["gemini"]["model_name"] = os.getenv(
                "GEMINI_MODEL_NAME"
            )

        # OpenAI APIキー
        if os.getenv("OPENAI_API_KEY"):
            # APIキーは設定ファイルには保存せず、環境変数から取得する
            pass

        # OpenAIモデル名の設定
        if os.getenv("OPENAI_MODEL_NAME"):
            if "llm" not in config:
                config["llm"] = {}
            if "models" not in config["llm"]:
                config["llm"]["models"] = {}
            if "openai" not in config["llm"]["models"]:
                config["llm"]["models"]["openai"] = {}

            config["llm"]["models"]["openai"]["model_name"] = os.getenv(
                "OPENAI_MODEL_NAME"
            )

        # ロギング設定
        if os.getenv("LOG_LEVEL"):
            if "logging" not in config:
                config["logging"] = {}
            config["logging"]["level"] = os.getenv("LOG_LEVEL")

        # 出力設定
        if os.getenv("OUTPUT_FORMAT"):
            if "output" not in config:
                config["output"] = {}
            config["output"]["format"] = os.getenv("OUTPUT_FORMAT")

    def get(self, key: str, default: Any = None) -> Any:
        """
        設定値を取得する。

        Args:
            key: 設定キー（ドット区切りで階層を指定可能）
            default: キーが存在しない場合のデフォルト値

        Returns:
            設定値
        """
        keys = key.split(".")
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_gemini_api_key(self) -> str:
        """
        Gemini APIキーを取得する。

        Returns:
            Gemini APIキー

        Raises:
            ValueError: APIキーが設定されていない場合
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "Gemini APIキーが設定されていません。.envファイルまたは環境変数で設定してください。"
            )
        return api_key

    def get_openai_api_key(self) -> str:
        """
        OpenAI APIキーを取得する。

        Returns:
            OpenAI APIキー

        Raises:
            ValueError: APIキーが設定されていない場合
        """
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI APIキーが設定されていません。.envファイルまたは環境変数で設定してください。"
            )
        return api_key

    def get_llm_config(self, llm_name: Optional[str] = None) -> Dict[str, Any]:
        """
        指定されたLLMの設定を取得する。

        Args:
            llm_name: LLM名。指定されない場合はデフォルトのLLMを使用。

        Returns:
            LLM設定
        """
        if llm_name is None:
            llm_name = self.get("llm.default", "gemini")

        llm_config = self.get(f"llm.models.{llm_name}", {})
        if not llm_config:
            raise ValueError(f"LLM '{llm_name}' の設定が見つかりません。")

        return llm_config

    def get_prompt_content(self, prompt_key: str) -> str:
        """
        指定されたプロンプトファイルの内容を取得する。

        Args:
            prompt_key: プロンプト設定のキー

        Returns:
            プロンプトファイルの内容

        Raises:
            FileNotFoundError: プロンプトファイルが見つからない場合
            ValueError: プロンプト設定のキーが見つからない場合
        """
        prompt_path_str = self.get(f"prompts.{prompt_key}")
        if not prompt_path_str:
            raise ValueError(f"プロンプト設定のキー '{prompt_key}' が見つかりません。")

        prompt_path = Path(prompt_path_str)
        if not prompt_path.exists():
            # configディレクトリからの相対パスも試す
            prompt_path = self.config_dir / prompt_path_str
            if not prompt_path.exists():
                raise FileNotFoundError(
                    f"プロンプトファイルが見つかりません: {prompt_path_str}"
                )

        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()


# シングルトンインスタンス
config = Config()
