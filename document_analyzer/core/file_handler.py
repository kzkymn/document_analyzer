import json
from pathlib import Path
from typing import List, Union

from .pair_check import PairCheckItem, PairCheckItemType

# 必要に応じて他のインポートも追加


class FileHandler:
    """ファイル入出力クラス"""

    def __init__(self, logger):
        self.logger = logger

    def save_items_to_file(
        self, items: List[PairCheckItem], output_path: Union[str, Path]
    ):
        """
        抽出された項目（条件またはファクト）をファイルに保存する。

        Args:
            items: 保存するPairCheckItemのリスト
            output_path: 出力先ファイルのパス
        """
        path = Path(output_path)

        # 親ディレクトリが存在しない場合は作成
        path.parent.mkdir(parents=True, exist_ok=True)

        # 項目をJSON形式に変換
        items_json = []
        for item in items:
            item_dict = {
                "id": item.id,
                "text": item.text,
                "parent_id": item.parent_id,
                "type": item.item_type.value,
            }
            if item.source:
                item_dict["source"] = item.source
            items_json.append(item_dict)

        # JSONファイルとして保存
        with open(path, "w", encoding="utf-8") as f:
            json.dump(items_json, f, ensure_ascii=False, indent=2)

        self.logger.info(f"抽出結果をJSON形式で保存しました: {path}")

    def load_items_from_file(
        self, file_path: Union[str, Path], item_type: PairCheckItemType = None
    ) -> List[PairCheckItem]:
        """
        ファイルから項目（条件またはファクト）を読み込む。

        Args:
            file_path: 読み込むファイルのパス
            item_type: 項目の種類（指定しない場合はファイル名から推測）

        Returns:
            読み込んだPairCheckItemのリスト
        """
        path = Path(file_path)

        # デフォルトファイル名の判定
        is_default_conditions = path.name == "conditions_output.json"
        is_default_facts = path.name == "facts_output.json"

        if is_default_conditions:
            self.logger.info("デフォルトの条件ファイルを読み込もうとしています")
        elif is_default_facts:
            self.logger.info("デフォルトのファクトファイルを読み込もうとしています")

        if not path.exists():
            if is_default_conditions or is_default_facts:
                self.logger.warning(
                    f"デフォルトの{'条件' if is_default_conditions else 'ファクト'}ファイルが見つからないためスキップします: {path}"
                )
            else:
                self.logger.error(f"ファイルが見つかりません: {path}")
            return []

        try:
            # JSONファイルとして読み込み
            with open(path, "r", encoding="utf-8") as f:
                items_json = json.load(f)

            items = []
            for item_dict in items_json:
                # 項目の種類を取得（ファイルに保存されている場合はそれを使用）
                item_type_value = item_dict.get("type")
                if item_type_value:
                    try:
                        item_type_obj = PairCheckItemType(item_type_value)
                    except ValueError:
                        item_type_obj = item_type
                else:
                    item_type_obj = item_type

                # PairCheckItemを作成
                item = PairCheckItem(
                    id=item_dict.get("id"),
                    text=item_dict.get("text", ""),
                    source=item_dict.get("source"),
                    item_type=item_type_obj,
                    parent_id=item_dict.get("parent_id"),
                )
                items.append(item)

            return items
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析エラー: {e}")
            self.logger.error(f"解析対象ファイル: {path}")
            return []
        except Exception as e:
            self.logger.error(f"ファイルの読み込み中にエラーが発生しました: {e}")
            return []
