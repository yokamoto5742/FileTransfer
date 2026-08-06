from pathlib import Path
from unittest.mock import patch

import pytest

from utils.config_manager import get_target_rules


def write_config(tmp_path: Path, content: str) -> Path:
    """テスト用のconfig.iniを作成"""
    config_file = tmp_path / "config.ini"
    config_file.write_text(content, encoding="utf-8")
    return config_file


@pytest.fixture
def config_factory(tmp_path):
    """指定した内容のconfig.iniを読み込ませるフィクスチャ"""

    def _factory(content: str):
        config_file = write_config(tmp_path, content)
        return patch("utils.config_manager.CONFIG_PATH", str(config_file))

    return _factory


class TestGetTargetRules:
    """get_target_rulesのテスト"""

    def test_single_target_without_filenames(self, config_factory):
        """filenameが空欄の場合は全ファイルが対象"""
        with config_factory("""
[Paths]
processing_dir = C:\\src
target_dir1 = C:\\dest\\A
filename1 =

[Rename]
pattern1 = _magnate
"""):
            rules = get_target_rules()

        assert len(rules) == 1
        assert rules[0].directory == Path(r"C:\dest\A")
        assert rules[0].filenames == frozenset()
        assert rules[0].suffix == "_magnate"
        assert rules[0].pattern is not None
        assert rules[0].pattern.pattern == "_magnate$"

    def test_multiple_targets_sorted_by_index(self, config_factory):
        """番号の昇順で取得される"""
        with config_factory("""
[Paths]
processing_dir = C:\\src
target_dir10 = C:\\dest\\J
filename10 =
target_dir2 = C:\\dest\\B
filename2 = test2.txt
target_dir1 = C:\\dest\\A
filename1 = test1.md

[Rename]
pattern1 =
pattern2 =
pattern10 =
"""):
            rules = get_target_rules()

        assert [str(rule.directory) for rule in rules] == [r"C:\dest\A", r"C:\dest\B", r"C:\dest\J"]

    def test_filenames_are_split_and_lowercased(self, config_factory):
        """カンマ区切りのファイル名が小文字化して分割される"""
        with config_factory("""
[Paths]
processing_dir = C:\\src
target_dir1 = C:\\dest\\A
filename1 = Test1.MD , test2.txt,

[Rename]
pattern1 =
"""):
            rules = get_target_rules()

        assert rules[0].filenames == frozenset({"test1.md", "test2.txt"})

    def test_pattern_per_target(self, config_factory):
        """ターゲットごとに異なるパターンを持つ"""
        with config_factory("""
[Paths]
processing_dir = C:\\src
target_dir1 = C:\\dest\\A
filename1 = test1.md
target_dir2 = C:\\dest\\B
filename2 =

[Rename]
pattern1 = _magnate
pattern2 = _backup
"""):
            rules = get_target_rules()

        assert rules[0].suffix == "_magnate"
        assert rules[1].suffix == "_backup"

    def test_empty_pattern_yields_no_pattern(self, config_factory):
        """patternが空欄の場合はサフィックスを追加しない"""
        with config_factory("""
[Paths]
processing_dir = C:\\src
target_dir1 = C:\\dest\\A
filename1 =

[Rename]
pattern1 =
"""):
            rules = get_target_rules()

        assert rules[0].suffix == ""
        assert rules[0].pattern is None

    def test_missing_pattern_key_yields_no_pattern(self, config_factory):
        """patternN自体が無い場合もサフィックスを追加しない"""
        with config_factory("""
[Paths]
processing_dir = C:\\src
target_dir1 = C:\\dest\\A
filename1 =

[Rename]
pattern2 = _magnate
"""):
            rules = get_target_rules()

        assert rules[0].pattern is None

    def test_missing_rename_section(self, config_factory):
        """Renameセクションが無くてもエラーにならない"""
        with config_factory("""
[Paths]
processing_dir = C:\\src
target_dir1 = C:\\dest\\A
filename1 =
"""):
            rules = get_target_rules()

        assert rules[0].pattern is None

    def test_pattern_with_trailing_dollar(self, config_factory):
        """末尾の$はサフィックスから除去される"""
        with config_factory("""
[Paths]
processing_dir = C:\\src
target_dir1 = C:\\dest\\A
filename1 =

[Rename]
pattern1 = _magnate$
"""):
            rules = get_target_rules()

        assert rules[0].suffix == "_magnate"
        assert rules[0].pattern is not None
        assert rules[0].pattern.pattern == "_magnate$"

    def test_no_target_dir_raises(self, config_factory):
        """target_dirNが1つも無い場合はValueError"""
        with config_factory("""
[Paths]
processing_dir = C:\\src

[Rename]
pattern1 =
"""):
            with pytest.raises(ValueError, match="移動先ディレクトリ"):
                get_target_rules()

    def test_unnumbered_target_dir_is_ignored(self, config_factory):
        """番号なしのtarget_dirは無視される"""
        with config_factory("""
[Paths]
processing_dir = C:\\src
target_dir = C:\\dest\\old

[Rename]
pattern1 =
"""):
            with pytest.raises(ValueError, match="移動先ディレクトリ"):
                get_target_rules()

    def test_invalid_pattern_raises(self, config_factory):
        """不正な正規表現はエラー"""
        import re

        with config_factory("""
[Paths]
processing_dir = C:\\src
target_dir1 = C:\\dest\\A
filename1 =

[Rename]
pattern1 = [invalid
"""):
            with pytest.raises(re.error):
                get_target_rules()
