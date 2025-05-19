import json
import re
from pathlib import Path
from typing import List, Tuple, Union

from ..llm.base import BaseLLMProcessor
from .pair_check import PairCheckItem, PairCheckItemType

# 必要に応じて他のインポートも追加


class ConditionDrivenExtractor:
    """条件駆動型ファクト抽出クラス"""

    def __init__(self, llm_processor: BaseLLMProcessor, logger):
        self.llm_processor = llm_processor
        self.logger = logger

    def _analyze_condition_for_granularity(self, condition: str) -> str:
        """
        条件を分析し、適切なファクト抽出の粒度を決定するためのプロンプト部分を生成する。

        Args:
            condition: 分析する条件

        Returns:
            ファクト抽出の粒度を指示するプロンプト部分
        """
        self.logger.info(f"条件「{condition}」の分析を開始します")

        # 条件を分析するためのプロンプト
        prompt = f"""
あなたは文書分析の専門家です。以下の条件を分析し、この条件を検証するために必要なファクト（事実）の適切な抽出粒度を決定してください。

# 条件
{condition}

# 指示
1. 上記の条件を分析し、この条件を検証するために必要なファクト（事実）の適切な抽出粒度を決定してください。
2. 条件の性質（定量的/定性的、具体的/抽象的など）を考慮してください。
3. 条件に含まれる重要なキーワードや概念を特定してください。
4. 以下の観点から、ファクト抽出の粒度に関する指示を作成してください：
   - ファクトの詳細度（詳細/概要）
   - ファクトの範囲（広範囲/限定的）
   - 数値や日付などの具体的な情報の重要性
   - 文脈情報の必要性
   - 階層構造の必要性

# 出力形式
以下の形式で、ファクト抽出の粒度に関する指示を3〜5行程度で出力してください。
これらの指示は、ファクト抽出のプロンプトに直接組み込まれます。

```
- [ファクトの詳細度に関する指示]
- [ファクトの範囲に関する指示]
- [具体的な情報の抽出に関する指示]
- [必要に応じて追加の指示]
```
"""

        # LLMを使用して条件を分析
        response = self.llm_processor.call_llm(prompt)
        text = response.get("text", "")

        # 出力からファクト抽出の粒度に関する指示を抽出
        granularity_instructions = ""
        in_instructions_block = False
        for line in text.splitlines():
            line = line.strip()
            if line == "```" and not in_instructions_block:
                in_instructions_block = True
                continue
            elif line == "```" and in_instructions_block:
                break
            elif in_instructions_block and line:
                granularity_instructions += line + "\n"

        # 指示が抽出できなかった場合はデフォルトの指示を使用
        if not granularity_instructions.strip():
            self.logger.warning(
                "条件の分析から粒度指示を抽出できませんでした。デフォルトの指示を使用します。"
            )
            granularity_instructions = """
- ファクトは、条件の検証に必要な詳細さで抽出してください。
- 条件に関連する具体的な数値、日付、名称などの情報を優先して抽出してください。
- 条件の文脈を理解するために必要な背景情報も含めてください。
"""

        self.logger.info("条件の分析が完了しました")
        return granularity_instructions.strip()

    def save_condition_driven_facts_to_file(
        self,
        condition_facts: List[Tuple[PairCheckItem, List[PairCheckItem]]],
        output_path: Union[str, Path],
    ):
        """
        条件駆動型のファクト抽出結果をファイルに保存する。

        Args:
            condition_facts: 条件とそれに関連するファクトのリストのタプルのリスト
            output_path: 出力先ファイルのパス
        """
        path = Path(output_path)

        # 親ディレクトリが存在しない場合は作成
        path.parent.mkdir(parents=True, exist_ok=True)

        # 条件駆動型のファクト抽出結果をJSON形式に変換
        result_json = []
        for condition, facts in condition_facts:
            condition_dict = {
                "id": condition.id,
                "text": condition.text,
                "type": condition.item_type.value,
                "facts": [],
            }
            if condition.source:
                condition_dict["source"] = condition.source

            # ファクトを追加
            for fact in facts:
                fact_dict = {
                    "id": fact.id,
                    "text": fact.text,
                    "parent_id": fact.parent_id,
                    "type": fact.item_type.value,
                }
                if fact.source:
                    fact_dict["source"] = fact.source
                condition_dict["facts"].append(fact_dict)

            result_json.append(condition_dict)

        # JSONファイルとして保存
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result_json, f, ensure_ascii=False, indent=2)

        self.logger.info(
            f"条件駆動型のファクト抽出結果をJSON形式で保存しました: {path}"
        )
