import json
from typing import Dict, List


class ResponseParser:
    """LLM応答解析クラス"""

    def __init__(self, logger):
        self.logger = logger

    def _parse_extraction_response(self, response: dict) -> List[dict]:
        """
        抽出応答を解析する。

        Args:
            response: LLMからの応答

        Returns:
            抽出された項目のリスト（辞書形式）
        """
        text = response.get("text", "")

        # JSONブロックを抽出
        json_block = ""
        in_json_block = False
        for line in text.splitlines():
            line = line.strip()
            if line == "```json" or line == "```":
                in_json_block = not in_json_block
                continue
            if in_json_block:
                json_block += line + "\n"

        # JSONブロックが見つからない場合は、テキスト全体をJSONとして解析を試みる
        if not json_block:
            json_block = text

        try:
            items = json.loads(json_block)
            return items
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析エラー: {e}")
            self.logger.error(f"解析対象テキスト: {json_block}")

            # エラーが発生した場合は、従来の方法でテキストを解析
            self.logger.warning("従来の方法でテキストを解析します")
            items = []
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("- "):
                    items.append(
                        {
                            "id": len(items) + 1,
                            "text": line[2:].strip(),
                            "parent_id": None,
                        }
                    )
            return items
