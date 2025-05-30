"""
基本LLMインターフェースモジュール。
様々なLLMの共通インターフェースを定義する。
"""

import abc
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..core.processor import AnalysisResult, LLMProcessor
from ..utils.config import config
from ..utils.logging import logger


class BaseLLMProcessor(LLMProcessor):
    """基本LLMプロセッサークラス"""

    def __init__(self, config, model_config: Optional[Dict[str, Any]] = None):
        """
        初期化

        Args:
            config: 設定オブジェクト
            model_config: モデル設定。指定されない場合は設定ファイルから取得。
        """
        super().__init__()
        self.config = config
        self.model_config = model_config or {}
        self.logger = logger

    def preprocess_reference_text(self, text: str) -> str:
        """
        参照テキストを前処理する。
        基本実装では、テキストをそのまま返す。

        Args:
            text: 参照テキスト

        Returns:
            前処理されたテキスト
        """
        # 基本的な前処理（空白行の削除、余分な空白の削除など）
        lines = text.splitlines()
        non_empty_lines = [line.strip() for line in lines if line.strip()]
        processed_text = "\n".join(non_empty_lines)

        return processed_text

    def preprocess_file(self, file_path: Union[str, Path]) -> str:
        """
        ファイルを前処理する。
        基本実装では、テキストファイルとして読み込む。

        Args:
            file_path: ファイルパス

        Returns:
            前処理されたファイル内容
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"ファイルが見つかりません: {file_path}")

        # テキストファイルとして読み込む
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            return content
        except UnicodeDecodeError:
            # バイナリファイルの場合はエラー
            raise ValueError(f"サポートされていないファイル形式です: {file_path}")

    def generate_prompt(
        self, reference_text: str, file_content: str, config_path: Optional[str] = None
    ) -> str:
        """
        プロンプトを生成する。

        Args:
            reference_text: 前処理された参照テキスト
            file_content: 前処理されたファイル内容
            config_path: 設定ファイルのパス

        Returns:
            生成されたプロンプト
        """
        # グローバルな設定インスタンスを使用する
        # config_pathパラメータは後方互換性のために残しておく
        from ..utils.config import config

        # グローバルな設定インスタンスを使用
        if config_path:
            import yaml

            with open(config_path, "r", encoding="utf-8") as f:
                local_config = yaml.safe_load(f)
        else:
            from ..utils.config import config

            local_config = config

        # テンプレートパスを取得
        template_path = None
        if (
            isinstance(local_config, dict)
            and "prompt" in local_config
            and "template_path" in local_config["prompt"]
        ):
            template_path = local_config["prompt"]["template_path"]
        self.logger.debug(f"Loaded template_path: {template_path}")
        self.logger.debug(f"Full local_config: {local_config}")
        if not template_path:
            self.logger.debug("template_path is not set, using default prompt")
            self.logger.warning(
                "プロンプトテンプレートのパスが指定されていません。デフォルトのプロンプトを使用します。"
            )
            return self._get_default_prompt(reference_text, file_content)

        # テンプレートパスを絶対パスに変換
        template_path_obj = Path(template_path)
        if not template_path_obj.is_absolute() and config_path:
            # 相対パスの場合、設定ファイルのディレクトリからの相対パスとして解釈
            config_dir = Path(config_path).parent
            template_path_obj = config_dir / template_path

        # テンプレートファイルが存在するか確認
        if not template_path_obj.exists():
            abs_path = template_path_obj.absolute()
            config_dir = Path(config_path).parent if config_path else Path.cwd()
            self.logger.warning(
                f"プロンプトテンプレートファイルが見つかりません: {abs_path}\n"
                f"設定ファイル内の prompt.template_path で正しいパスを指定してください。\n"
                f"相対パスの場合は、設定ファイルのディレクトリ {config_dir} からの相対パスとして解釈されます。"
            )
            return self._get_default_prompt(reference_text, file_content)

        # テンプレートファイルを読み込む
        try:
            with open(template_path_obj, "r", encoding="utf-8") as f:
                template = f.read()

            # テンプレートに変数を埋め込む
            prompt = template.format(
                reference_text=reference_text, file_content=file_content
            )

            return prompt

        except Exception as e:
            self.logger.error(
                f"プロンプトテンプレートの読み込み中にエラーが発生しました: {str(e)}"
            )
            # エラーが発生した場合はデフォルトのプロンプトを使用
            return self._get_default_prompt(reference_text, file_content)

    def _get_default_prompt(self, reference_text: str, file_content: str) -> str:
        """
        デフォルトのプロンプトを取得する。

        Args:
            reference_text: 前処理された参照テキスト
            file_content: 前処理されたファイル内容

        Returns:
            デフォルトのプロンプト
        """
        from document_analyzer.utils.config import config

        prompt_template = config.get_prompt_content("default_analysis")
        prompt = prompt_template.format(
            reference_text=reference_text, file_content=file_content
        )
        return prompt

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

    def should_extract_items(
        self,
        file_path: Union[str, Path],
        file_size: int,
        file_head: str,
        source_context: Optional[str] = None,
    ) -> tuple[bool, str]:
        """
        ファイルの内容から条件またはファクトの抽出が必要か判断する。
        LLMを使用して判断を行う。

        Args:
            file_path: ファイルパス
            file_size: ファイルサイズ (バイト)
            file_head: ファイル内容の冒頭部分
            source_context: ターゲットファイルの場合、ソースファイルの内容または抽出された条件

        Returns:
            (抽出要否, 判断根拠) のタプル。抽出が必要な場合はTrue、そうでない場合はFalse
        """
        self.logger.debug(f"LLMに抽出要否を問い合わせます: {file_path}")

        from document_analyzer.utils.config import config

        prompt_template = config.get_prompt_content("should_extract")
        # source_contextがNoneまたは空文字列の場合は"なし"を渡す
        formatted_source_context = source_context if source_context else "なし"

        prompt = prompt_template.format(
            file_path=file_path,
            file_size=file_size,
            file_head=file_head,
            source_context=formatted_source_context,
        )

        try:
            response = self.call_llm(prompt)
            text = response.get("text", "")

            # 抽出要否の判断結果
            need_extract = False
            if "## 抽出要否" in text:
                extract_section = (
                    text.split("## 抽出要否")[1].split("##")[0].strip().lower()
                )
                need_extract = "yes" in extract_section
            else:
                self.logger.warning(
                    f"LLMからの応答形式が不正です。抽出要否を判断できませんでした: {text}"
                )
                # 応答形式が不正な場合は、安全側に倒して抽出が必要と判断する
                need_extract = True

            # 判断根拠の抽出
            reason = "判断根拠が提供されていません"
            if "## 判断根拠" in text:
                reason_section = text.split("## 判断根拠")[1].split("##")[0].strip()
                reason = reason_section if reason_section else reason

            self.logger.debug(
                f"LLMの判断: {file_path} から抽出{'が必要' if need_extract else 'は不要'}です。根拠: {reason}"
            )
            return need_extract, reason

        except Exception as e:
            error_msg = f"LLMによる抽出要否判断中にエラーが発生しました: {str(e)}"
            self.logger.error(error_msg)
            # エラーが発生した場合も、安全側に倒して抽出が必要と判断する
            return True, error_msg

    @abc.abstractmethod
    def call_llm(self, prompt: str) -> Dict[str, Any]:
        """
        LLMを呼び出す。
        サブクラスで実装する必要がある。

        Args:
            prompt: プロンプト

        Returns:
            LLMからの応答
        """
        pass

    def parse_response(self, response: Dict[str, Any]) -> AnalysisResult:
        """
        LLMの応答を解析する。
        基本実装では、応答テキストを解析して結果を構造化する。

        Args:
            response: LLMからの応答

        Returns:
            分析結果
        """
        # サブクラスで実装する必要がある
        raise NotImplementedError("サブクラスで実装する必要があります")

    @abc.abstractmethod
    def call_critic_llm(self, prompt: str) -> Dict[str, Any]:
        """
        Critic LLMを呼び出す。
        サブクラスで実装する必要がある。

        Args:
            prompt: プロンプト

        Returns:
            LLMからの応答
        """
        pass
