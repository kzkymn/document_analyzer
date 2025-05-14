"""
テキスト読み込み時にエンコーディングを自動判定するユーティリティ

主な方針
1. UTF-8 で読めるならそれを採用
2. 失敗した場合はシステム既定エンコーディング (locale.getpreferredencoding) を試す
3. さらに Windows 日本語環境で一般的な CP932 (Shift-JIS) も試す
4. すべて失敗した場合は UTF-8 で errors="ignore" で読込み

本関数を使うことで「UTF-8 / Shift-JIS 混在プロジェクト」でも
`UnicodeDecodeError` を抑制しつつ内容を取得できる。
"""

from __future__ import annotations

import locale
from pathlib import Path
from typing import Iterable, List, Union


def _merge_encodings(candidates: Iterable[str]) -> List[str]:
    """重複を除いて優先順にエンコーディング候補を並べ替える"""
    seen: set[str] = set()
    ordered: List[str] = []
    for enc in candidates:
        key = enc.lower()
        if key not in seen:
            ordered.append(enc)
            seen.add(key)
    return ordered


def read_text_auto(
    path: Union[str, Path], extra_encodings: Iterable[str] | None = None
) -> str:
    """
    与えられたファイルを複数エンコーディングで試行しながら読み込む。

    Parameters
    ----------
    path: str | Path
        読み込み対象ファイルパス
    extra_encodings: Iterable[str] | None
        追加で試したいエンコーディング名のリスト (先頭が最優先)

    Returns
    -------
    str
        ファイルのテキスト内容。すべてのデコードが失敗した場合は
        UTF-8 errors=\"ignore\" で読み込んだ結果を返す。
    """
    p = Path(path)

    # 試行順: extra -> utf-8 -> locale -> cp932
    preferred_locale = locale.getpreferredencoding(False) or "utf-8"
    candidates: List[str] = []
    if extra_encodings:
        candidates.extend(extra_encodings)
    candidates.extend(["utf-8", preferred_locale, "cp932"])
    encodings = _merge_encodings(candidates)

    last_error: UnicodeDecodeError | None = None
    for enc in encodings:
        try:
            return p.read_text(encoding=enc)
        except UnicodeDecodeError as err:
            last_error = err
            continue

    # すべて失敗した場合は UTF-8 errors=\"ignore\" で読込む
    return p.read_text(encoding="utf-8", errors="ignore")
