import re
from typing import Dict, List

# 必要に応じて他のインポートも追加


class StructureAnalyzer:
    """文書構造解析クラス"""

    def __init__(self, logger):
        self.logger = logger

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
