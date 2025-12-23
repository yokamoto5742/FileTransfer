import configparser
import os
import re
import sys


def get_config_path():
    if getattr(sys, 'frozen', False):
        # PyInstallerでビルドされた実行ファイルの場合
        base_path = sys._MEIPASS
    else:
        # 通常のPythonスクリプトとして実行される場合
        base_path = os.path.dirname(__file__)

    return os.path.join(base_path, 'config.ini')


CONFIG_PATH = get_config_path()


def load_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    try:
        with open(CONFIG_PATH, encoding='utf-8') as f:
            config.read_file(f)
    except FileNotFoundError:
        print(f"設定ファイルが見つかりません: {CONFIG_PATH}")
        raise
    except configparser.Error as e:
        print(f"設定ファイルの解析中にエラーが発生しました: {e}")
        raise
    return config


def save_config(config: configparser.ConfigParser):
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
    except IOError as e:
        print(f"設定ファイルの保存中にエラーが発生しました: {e}")
        raise


def get_src_dir() -> str:
    """監視対象のディレクトリパスを取得"""
    config = load_config()
    return config.get('Paths', 'processing_dir')


def get_rename_patterns() -> list[re.Pattern]:
    """ファイル名変換用の正規表現パターンリストを取得"""
    config = load_config()
    pattern_items = []

    # pattern1, pattern2... の形式で全パターンを取得
    for key in config['Rename']:
        if key.startswith('pattern'):
            pattern_str = config.get('Rename', key)

            # パターンが$で終わっていない場合は末尾マッチとして$を追加
            if not pattern_str.endswith('$'):
                pattern_str = pattern_str + '$'

            try:
                pattern_items.append((pattern_str, re.compile(pattern_str)))
            except re.error as e:
                print(f"正規表現パターンが無効です: {pattern_str}")
                print(f"エラー: {e}")
                raise

    # より具体的なパターン（長いパターン）を先に適用するため、パターン文字列長の降順でソート
    pattern_items.sort(key=lambda x: len(x[0]), reverse=True)

    return [pattern for _, pattern in pattern_items]


def get_wait_time() -> float:
    """ファイル書き込み完了を待つ時間を取得（秒）"""
    config = load_config()
    return config.getfloat('App', 'wait_time', fallback=0.5)


def get_config_value(config: configparser.ConfigParser, section: str, key: str, default=None):
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
