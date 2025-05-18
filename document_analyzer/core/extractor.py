"""
テキスト抽出モジュール。
テキストから条件やファクトを抽出するクラスを提供する。
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from ..llm.base import BaseLLMProcessor
from .pair_check import PairCheckItem, PairCheckItemType


class TextExtractor:
    """テキスト抽出クラス"""

    def __init__(self, llm_processor: BaseLLMProcessor):
        """
        初期化

        Args:
            llm_processor: LLMプロセッサー
        """
        self.llm_processor = llm_processor
        self.logger = llm_processor.logger

    def extract_conditions(
        self, text: str, source: Optional[str] = None
    ) -> List[PairCheckItem]:
        """
        テキストからチェック条件を抽出する。

        Args:
            text: テキスト
            source: 出典（ファイルパスなど）

        Returns:
            チェック条件のリスト
        """
        self.logger.info("チェック条件の抽出を開始します")

        # 文書構造を解析
        structured_blocks = self._analyze_document_structure(text)

        # LLMを使用して条件を抽出
        prompt = self._get_condition_extraction_prompt(text, structured_blocks)
        response = self.llm_processor.call_llm(prompt)
        conditions_dict = self._parse_extraction_response(response)

        # PairCheckItemのリストに変換
        result = []
        for condition in conditions_dict:
            item = PairCheckItem(
                text=condition["text"],
                source=source,
                item_type=PairCheckItemType.CONDITION,
                id=condition.get("id"),
                parent_id=condition.get("parent_id"),
            )
            result.append(item)

        # 親子関係を設定
        for item in result:
            if item.parent_id is not None:
                # 親アイテムを探す
                parent = next((p for p in result if p.id == item.parent_id), None)
                if parent:
                    if parent.children is None:
                        parent.children = []
                    parent.children.append(item)

        self.logger.info(f"{len(result)}個のチェック条件を抽出しました")
        return result

    def extract_facts(
        self, text: str, source: Optional[str] = None
    ) -> List[PairCheckItem]:
        """
        テキストからファクトを抽出する。

        Args:
            text: テキスト
            source: 出典（ファイルパスなど）

        Returns:
            ファクトのリスト
        """
        self.logger.info("ファクトの抽出を開始します")

        # 文書構造を解析
        structured_blocks = self._analyze_document_structure(text)

        # LLMを使用してファクトを抽出
        prompt = self._get_fact_extraction_prompt(text, structured_blocks)
        response = self.llm_processor.call_llm(prompt)
        facts_dict = self._parse_extraction_response(response)

        # PairCheckItemのリストに変換
        result = []
        for fact in facts_dict:
            item = PairCheckItem(
                text=fact["text"],
                source=source,
                item_type=PairCheckItemType.FACT,
                id=fact.get("id"),
                parent_id=fact.get("parent_id"),
            )
            result.append(item)

        # 親子関係を設定
        for item in result:
            if item.parent_id is not None:
                # 親アイテムを探す
                parent = next((p for p in result if p.id == item.parent_id), None)
                if parent:
                    if parent.children is None:
                        parent.children = []
                    parent.children.append(item)

        self.logger.info(f"{len(result)}個のファクトを抽出しました")
        return result

    def _get_condition_extraction_prompt(
        self, text: str, structured_blocks: List[Dict]
    ) -> str:
        """
        チェック条件抽出用のプロンプトを取得する。

        Args:
            text: テキスト
            structured_blocks: 構造情報付きテキストブロックのリスト

        Returns:
            プロンプト
        """
        from document_analyzer.utils.config import config

        # 構造情報の要約を作成
        structure_summary = self._create_structure_summary(structured_blocks)

        # プロンプトテンプレートを取得
        prompt_template = config.get_prompt_content("condition_extraction")

        # テンプレートに値を埋め込む
        prompt = prompt_template.format(text=text, structure_summary=structure_summary)

        return prompt

    def _get_fact_extraction_prompt(
        self, text: str, structured_blocks: List[Dict]
    ) -> str:
        """
        ファクト抽出用のプロンプトを取得する。

        Args:
            text: テキスト
            structured_blocks: 構造情報付きテキストブロックのリスト

        Returns:
            プロンプト
        """
        from document_analyzer.utils.config import config

        # 構造情報の要約を作成
        structure_summary = self._create_structure_summary(structured_blocks)

        # プロンプトテンプレートを取得
        prompt_template = config.get_prompt_content("fact_extraction")

        # テンプレートに値を埋め込む
        prompt = prompt_template.format(text=text, structure_summary=structure_summary)

        return prompt

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
            import json

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

    def _analyze_document_structure(self, text: str) -> List[Dict]:
        """
        入力テキストの構造（章、項、箇条書きなど）を解析する。

        Args:
            text: 解析するテキスト

        Returns:
            構造情報付きテキストブロックのリスト
            例: [{"text": "...", "structure": {"type": "section", "level": 1, "title": "はじめに"}}, ...]
        """
        self.logger.info("文書構造の解析を開始します")
        structured_blocks = []
        current_section_title = ""
        current_section_level = 0
        section_stack = []  # (level, title) のタプルを保持

        lines = text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # 見出しの判定
            heading_match = re.match(r"^(#+)\s+(.*)$", line)
            if heading_match:
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()

                # より上位の見出しが現れた場合、スタックを調整
                while section_stack and section_stack[-1][0] >= level:
                    section_stack.pop()

                section_stack.append((level, title))
                current_section_title = " - ".join([t for _, t in section_stack])
                current_section_level = level

                structured_blocks.append(
                    {
                        "text": line,
                        "structure": {
                            "type": "heading",
                            "level": level,
                            "title": title,
                            "full_title": current_section_title,
                        },
                    }
                )
                i += 1
                continue

            # 箇条書きの判定
            # Markdownのリスト形式 (- , * , + , 数字.) に対応
            list_item_match = re.match(r"^(\s*)[-\*\+]\s+(.*)$", line)
            ordered_list_item_match = re.match(r"^(\s*)\d+\.\s+(.*)$", line)

            if list_item_match or ordered_list_item_match:
                match = list_item_match if list_item_match else ordered_list_item_match
                indent = len(match.group(1))
                list_text = match.group(2).strip()
                list_level = indent // 2 + 1  # インデント2つで1レベルと仮定

                # 複数行にわたる箇条書きアイテムを結合
                current_list_item_text = list_text
                j = i + 1
                while j < len(lines):
                    next_line = lines[j]
                    # 次の行が現在の箇条書きアイテムのインデントと同じかそれ以上の場合、結合
                    if next_line.startswith(" " * indent) and not re.match(
                        r"^\s*([-\*\+]|\d+\.)\s+", next_line.strip()
                    ):
                        current_list_item_text += "\n" + next_line.strip()
                        j += 1
                    else:
                        break

                structured_blocks.append(
                    {
                        "text": lines[i:j],  # 元の複数行を保持
                        "structure": {
                            "type": "list_item",
                            "level": list_level,
                            "section_title": current_section_title,
                            "section_level": current_section_level,
                        },
                    }
                )
                i = j
                continue

            # 地の文
            if line:  # 空行でない場合
                # 複数行にわたる地の文を結合
                current_paragraph_lines = [line]
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    # 次の行が空行でなく、見出しや箇条書きでない場合、結合
                    if (
                        next_line
                        and not re.match(r"^(#+)\s+(.*)$", next_line)
                        and not re.match(r"^(\s*)[-\*\+]|\d+\.\s+", next_line)
                    ):
                        current_paragraph_lines.append(lines[j])
                        j += 1
                    else:
                        break

                structured_blocks.append(
                    {
                        "text": current_paragraph_lines,  # 元の複数行を保持
                        "structure": {
                            "type": "paragraph",
                            "section_title": current_section_title,
                            "section_level": current_section_level,
                        },
                    }
                )
                i = j
                continue

            # 空行はスキップ
            i += 1

        self.logger.info("文書構造の解析が完了しました")
        return structured_blocks

    def _create_structure_summary(self, structured_blocks: List[Dict]) -> str:
        """
        構造情報の要約を作成する。

        Args:
            structured_blocks: 構造情報付きテキストブロックのリスト

        Returns:
            構造情報の要約
        """
        summary = "文書は以下の構造を持っています：\n\n"

        # 見出し構造の要約
        headings = [
            block
            for block in structured_blocks
            if block["structure"]["type"] == "heading"
        ]
        if headings:
            summary += "## 見出し構造\n"
            for heading in headings:
                level = heading["structure"]["level"]
                title = heading["structure"]["title"]
                summary += f"{'  ' * (level - 1)}- {title}\n"
            summary += "\n"

        # 箇条書きの要約
        list_items = [
            block
            for block in structured_blocks
            if block["structure"]["type"] == "list_item"
        ]
        if list_items:
            summary += "## 箇条書き項目\n"
            summary += f"文書内に{len(list_items)}個の箇条書き項目があります。\n"
            summary += "箇条書き項目は、それが属する見出しのコンテキストを考慮して抽出してください。\n\n"

        # 段落の要約
        paragraphs = [
            block
            for block in structured_blocks
            if block["structure"]["type"] == "paragraph"
        ]
        if paragraphs:
            summary += "## 段落\n"
            summary += f"文書内に{len(paragraphs)}個の段落があります。\n"
            summary += (
                "段落は、それが属する見出しのコンテキストを考慮して抽出してください。\n"
            )

        return summary

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
        import json

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

        # ファイル名から種類を推測（指定がない場合）
        if item_type is None:
            if "condition" in path.name.lower():
                item_type = PairCheckItemType.CONDITION
            else:
                item_type = PairCheckItemType.FACT

        try:
            # JSONファイルとして読み込み
            import json

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
                    text=item_dict["text"],
                    source=item_dict.get("source", str(path)),
                    item_type=item_type_obj,
                    id=item_dict.get("id"),
                    parent_id=item_dict.get("parent_id"),
                )
                items.append(item)

            # 親子関係を設定
            for item in items:
                if item.parent_id is not None:
                    # 親アイテムを探す
                    parent = next((p for p in items if p.id == item.parent_id), None)
                    if parent:
                        if parent.children is None:
                            parent.children = []
                        parent.children.append(item)

            self.logger.info(
                f"{len(items)}個の項目をJSONファイルから読み込みました: {path}"
            )
            return items

        except json.JSONDecodeError:
            # JSONとして解析できない場合は、従来の方法でテキストとして読み込む
            self.logger.warning(
                f"JSONとして解析できないため、テキストとして読み込みます: {path}"
            )
            items = []
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:  # 空行でなければ
                        items.append(
                            PairCheckItem(
                                text=line, source=str(path), item_type=item_type
                            )
                        )

            self.logger.info(
                f"{len(items)}個の項目をテキストファイルから読み込みました: {path}"
            )
            return items

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
        import json

        with open(path, "w", encoding="utf-8") as f:
            json.dump(result_json, f, ensure_ascii=False, indent=2)

        self.logger.info(
            f"条件駆動型のファクト抽出結果をJSON形式で保存しました: {path}"
        )
