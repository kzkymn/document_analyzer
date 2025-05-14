"""
ロギングモジュール。
アプリケーション全体で使用するロガーを設定する。
"""

import logging
import sys
from pathlib import Path
from typing import Optional

from .config import config


def setup_logger(
    name: str = "document_analyzer", log_file: Optional[str] = None
) -> logging.Logger:
    """
    ロガーを設定する。

    Args:
        name: ロガー名
        log_file: ログファイルのパス。指定されない場合は設定から取得。

    Returns:
        設定されたロガー
    """
    # 設定からログレベルを取得
    log_level_str = config.get("logging.level", "INFO")
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)

    # ロガーを取得
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # ハンドラーが既に設定されている場合は何もしない
    if logger.handlers:
        return logger

    # フォーマッターを作成
    log_format = config.get(
        "logging.format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    formatter = logging.Formatter(log_format)

    # コンソールハンドラーを追加
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # ファイルハンドラーを追加（指定されている場合）
    if log_file is None:
        log_file = config.get("logging.file")

    if log_file:
        # ログディレクトリが存在しない場合は作成
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# デフォルトロガー
logger = setup_logger()
