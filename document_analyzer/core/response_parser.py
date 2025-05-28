import json
import re
from pathlib import Path  # pathlibモジュールを追加
from typing import Dict, List

from pydantic import ValidationError

from .pair_check import PairCheckItem, PairCheckItemType


class ResponseParser:
    """LLM応答解析クラス"""

    def __init__(self, logger):
        self.logger = logger

    def _parse_extraction_response(self, response: dict) -> List[dict]:
        """
        抽出応答を解析する。Pydanticスキーマでバリデーションを行う。

        Args:
            response: LLMからの応答

        Returns:
            抽出された項目のリスト（辞書形式）
        """
        text = response.get("text", "")
        self.logger.debug(f"LLMからの生応答テキスト:\n{text}")

        # LLMからの生応答を一時ファイルに書き出す
        try:
            output_dir = Path("temp_llm_responses")
            output_dir.mkdir(exist_ok=True)
            # タイムスタンプをファイル名に含めることで、複数の応答を区別できるようにする
            import datetime

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            output_file = output_dir / f"llm_response_{timestamp}.log"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(text)
            self.logger.info(f"LLMからの生応答をファイルに保存しました: {output_file}")
        except Exception as e:
            self.logger.error(f"LLM応答の保存中にエラーが発生しました: {e}")

        # 正規表現でJSONブロックを抽出
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            json_block = match.group(1).strip()
            self.logger.debug("JSONブロックを抽出しました。")
        else:
            # ```json ... ``` 形式が見つからない場合、テキスト全体をJSONとして解析を試みる
            json_block = text.strip()
            self.logger.debug(
                "JSONブロックが見つからなかったため、テキスト全体をJSONとして解析を試みます。"
            )

        self.logger.debug(f"解析対象のJSONブロック:\n{json_block}")

        try:
            # Pydanticモデルでバリデーション
            parsed_items = json.loads(json_block)
            validated_items = []
            for item in parsed_items:
                # condition_idが存在すれば、それをPairCheckItemのcondition_idsにマッピング
                if "condition_id" in item:
                    item["condition_ids"] = item.pop("condition_id")  # キー名を変更
                validated_items.append(PairCheckItem(**item))
            return validated_items
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析エラー: {e}")
            self.logger.error(
                f"解析対象テキスト (抽出されたJSONブロック):\n{json_block}"
            )
            self.logger.error(
                f"LLMからの生応答テキスト (全体):\n{text}"
            )  # 元の生応答全体をログ出力
            raise ValueError(f"LLM応答のJSON形式が不正です: {e}")
        except ValidationError as e:
            self.logger.error(f"Pydanticバリデーションエラー: {e}")
            self.logger.error(
                f"解析対象テキスト (抽出されたJSONブロック):\n{json_block}"
            )
            self.logger.error(
                f"LLMからの生応答テキスト (全体):\n{text}"
            )  # 元の生応答全体をログ出力
            raise ValueError(f"LLM応答のスキーマが不正です: {e}")

    def _post_process_extracted_items(
        self, items: List[PairCheckItem]
    ) -> List[PairCheckItem]:
        """
        抽出されたアイテムに対して後処理を行う。
        （重複排除、類似アイテムの統合、重要度の低いアイテムのフィルタリングなど）

        Args:
            items: 抽出されたPairCheckItemのリスト

        Returns:
            後処理されたPairCheckItemのリスト
        """
        self.logger.info(f"後処理を開始します。処理前のアイテム数: {len(items)}")

        # 1. 重複排除 (テキストが完全に一致するものを排除)
        unique_items_map = {item.text: item for item in items}
        unique_items = list(unique_items_map.values())
        self.logger.info(f"重複排除後アイテム数: {len(unique_items)}")

        # 2. 類似アイテムの統合 (ここでは簡易的に、より高度な類似度判定は別途実装)
        # 例: "AはBである" と "AはBだ" を統合するロジックなど
        # 現状は重複排除で対応できる範囲に留める

        # 3. 重要度の低いアイテムのフィルタリング (例: 短すぎる、一般的な表現すぎるなど)
        # ここでは例として、テキストが短すぎるものをフィルタリング
        filtered_items = [item for item in unique_items if len(item.text) > 5]
        self.logger.info(f"フィルタリング後アイテム数: {len(filtered_items)}")

        self.logger.info("後処理が完了しました。")
        return filtered_items
