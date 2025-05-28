import re
from typing import Dict, List

# 必要に応じて他のインポートも追加


class StructureAnalyzer:
    """文書構造解析クラス"""

    def __init__(self, logger, chunk_size: int = 4000, chunk_overlap: int = 200):
        self.logger = logger
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def should_chunk_text(self, text: str) -> bool:
        """
        テキストがチャンク分割を必要とするほど長いかどうかを判断する。

        Args:
            text: 判断するテキスト

        Returns:
            bool: チャンク分割が必要な場合はTrue、そうでない場合はFalse
        """
        # ここでは単純に文字数で判断するが、より複雑なロジックも可能
        return len(text) > self.chunk_size

    def chunk_text(self, text: str) -> List[str]:
        """
        テキストを文書構造（見出し、段落、箇条書き）を考慮してチャンクに分割する。

        Args:
            text: 分割するテキスト

        Returns:
            List[str]: テキストチャンクのリスト
        """
        self.logger.info(
            f"文書構造を考慮してテキストをチャンクに分割します (チャンクサイズ: {self.chunk_size}, オーバーラップ: {self.chunk_overlap})"
        )
        structured_blocks = self._analyze_document_structure(text)
        chunks = []
        current_chunk_lines = []
        current_chunk_length = 0

        for block in structured_blocks:
            # block["text"]はリストの場合と文字列の場合があるため、常にリストとして扱う
            block_lines = (
                block["text"] if isinstance(block["text"], list) else [block["text"]]
            )
            # 各行の長さに改行文字の分も加算して正確な長さを計算
            block_content_length = (
                sum(len(line) + 1 for line in block_lines) if block_lines else 0
            )

            # 現在のチャンクにブロックを追加するとchunk_sizeを超える場合
            # かつ、現在のチャンクが空でない場合（最初のブロックでいきなり超えるのを避ける）
            if (
                current_chunk_length + block_content_length > self.chunk_size
                and current_chunk_lines
            ):
                # 現在のチャンクを確定
                chunks.append("\n".join(current_chunk_lines))
                self.logger.debug(f"チャンク確定 (長さ: {current_chunk_length})")

                # オーバーラップ処理
                # 前のチャンクの末尾を新しいチャンクの先頭に含める
                overlap_lines = []
                overlap_length = 0
                # 後ろからオーバーラップサイズ分だけ行を追加
                # 行の順序を維持するため、逆順で追加し、最後に反転させる
                temp_overlap_lines = []
                for line in reversed(current_chunk_lines):
                    line_length = len(line) + 1  # +1 for newline
                    if overlap_length + line_length <= self.chunk_overlap:
                        temp_overlap_lines.append(line)
                        overlap_length += line_length
                    else:
                        break
                overlap_lines = list(reversed(temp_overlap_lines))  # 正しい順序に戻す

                current_chunk_lines = overlap_lines
                current_chunk_length = overlap_length
                self.logger.debug(f"オーバーラップ追加 (長さ: {current_chunk_length})")

            # ブロックを現在のチャンクに追加
            current_chunk_lines.extend(block_lines)
            current_chunk_length += block_content_length

        # 最後のチャンクを追加
        if current_chunk_lines:
            chunks.append("\n".join(current_chunk_lines))

        self.logger.info(f"{len(chunks)}個のチャンクに分割しました。")
        return chunks

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
