from __future__ import annotations

import configparser
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Pattern


TARGET_DIR_KEY = re.compile(r"^target_dir(\d+)$")


@dataclass(frozen=True)
class TargetRule:
    """移動先ディレクトリと、そこへ移動する条件・リネーム設定"""

    directory: Path
    # 移動対象のファイル名（小文字）。空の場合は全ファイルが対象
    filenames: frozenset[str]
    # ファイル名末尾（拡張子の前）に追加する文字列。空の場合は追加しない
    suffix: str
    # サフィックスが既に付いているかの判定用。suffixが空の場合はNone
    pattern: Optional[Pattern[str]]


def get_config_path() -> str:
    if getattr(sys, "frozen", False):
        # PyInstallerでビルドされた実行ファイルの場合
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    else:
        # 通常のPythonスクリプトとして実行される場合
        base_path = os.path.dirname(__file__)

    return os.path.join(base_path, "config.ini")


CONFIG_PATH = get_config_path()


def load_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            config.read_file(f)
    except FileNotFoundError:
        print(f"設定ファイルが見つかりません: {CONFIG_PATH}")
        raise
    except configparser.Error as e:
        print(f"設定ファイルの解析中にエラーが発生しました: {e}")
        raise
    return config


def save_config(config: configparser.ConfigParser) -> None:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as configfile:
            config.write(configfile)
    except IOError as e:
        print(f"設定ファイルの保存中にエラーが発生しました: {e}")
        raise


def get_src_dir() -> str:
    """監視対象のディレクトリパスを取得"""
    config = load_config()
    return config.get("Paths", "processing_dir")


def _parse_filenames(value: str) -> frozenset[str]:
    """カンマ区切りのファイル名指定を小文字の集合に変換"""
    return frozenset(name.strip().lower() for name in value.split(",") if name.strip())


def _compile_pattern(suffix: str) -> Optional[Pattern[str]]:
    """サフィックスが既に付いているかを判定する正規表現を生成"""
    if not suffix:
        return None

    # パターンが$で終わっていない場合は末尾マッチとして$を追加
    pattern_str = suffix if suffix.endswith("$") else suffix + "$"
    try:
        return re.compile(pattern_str)
    except re.error as e:
        print(f"正規表現パターンが無効です: {pattern_str}")
        print(f"エラー: {e}")
        raise


def _build_target_rule(config: configparser.ConfigParser, index: str) -> TargetRule:
    """target_dirN に対応する振り分けルールを組み立てる"""
    filenames = _parse_filenames(config.get("Paths", f"filename{index}", fallback=""))

    suffix = ""
    if config.has_section("Rename"):
        suffix = config.get("Rename", f"pattern{index}", fallback="").strip()
    # 設定値が$付きでもサフィックスとしては$を除いた文字列を使う
    suffix = suffix.rstrip("$")

    return TargetRule(
        directory=Path(config.get("Paths", f"target_dir{index}")),
        filenames=filenames,
        suffix=suffix,
        pattern=_compile_pattern(suffix),
    )


def get_target_rules() -> list[TargetRule]:
    """移動先ディレクトリごとの振り分けルールを番号の昇順で取得"""
    config = load_config()

    indexed_rules = []
    for key in config["Paths"]:
        matched = TARGET_DIR_KEY.match(key)
        if matched:
            index = matched.group(1)
            indexed_rules.append((int(index), _build_target_rule(config, index)))

    if not indexed_rules:
        raise ValueError("移動先ディレクトリ（target_dir1など）が設定されていません")

    indexed_rules.sort(key=lambda item: item[0])
    return [rule for _, rule in indexed_rules]


def get_wait_time() -> float:
    """ファイル書き込み完了を待つ時間を取得（秒）"""
    config = load_config()
    return config.getfloat("App", "wait_time", fallback=0.5)


def get_config_value(
    config: configparser.ConfigParser, section: str, key: str, default: Any = None
) -> Any:
    """設定値を取得する汎用ヘルパー関数"""
    if not config.has_option(section, key):
        return default

    # デフォルト値の型に応じて適切な変換を行う
    if isinstance(default, bool):
        return config.getboolean(section, key)
    elif isinstance(default, int):
        return config.getint(section, key)
    elif isinstance(default, float):
        return config.getfloat(section, key)
    else:
        return config.get(section, key)
