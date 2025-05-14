"""
設定管理モジュールのテスト
"""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from document_analyzer.utils.config import Config


def test_load_config_from_path():
    """指定されたパスから設定ファイルを読み込めることをテスト"""
    # 一時的な設定ファイルを作成
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as temp:
        config_data = {
            "prompt": {
                "template_path": "test_prompt.txt",
                "description": "テスト用設定"
            },
            "logging": {
                "level": "INFO"
            },
            "llm": {
                "default": "gemini",
                "models": {
                    "gemini": {
                        "model_name": "gemini-2.0-flash"
                    }
                }
            }
        }
        yaml.dump(config_data, temp, default_flow_style=False)
    
    try:
        # 設定を読み込む
        config = Config(temp.name)
        
        # 設定値を確認
        assert config.get("prompt.template_path") == "test_prompt.txt"
        assert config.get("prompt.description") == "テスト用設定"
    
    finally:
        # 一時ファイルを削除
        os.unlink(temp.name)


def test_config_file_not_found():
    """存在しない設定ファイルを指定した場合にエラーが発生することをテスト"""
    with pytest.raises(FileNotFoundError):
        Config("non_existent_config.yaml")