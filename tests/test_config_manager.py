from pathlib import Path
from unittest.mock import patch

import pytest

from utils.config_manager import get_watch_rules


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


class TestGetWatchRulesSources:
    """監視元セクションの解釈テスト"""

    def test_single_watch_section(self, config_factory):
        """監視元と移動先が1つずつ取得される"""
        with config_factory("""
[Watch1]
processing_dir = C:\\src
target_dir1 = C:\\dest\\A
filename1 =
pattern1 = _magnate
"""):
            rules = get_watch_rules()

        assert len(rules) == 1
        assert rules[0].source == Path(r"C:\src")
        assert len(rules[0].targets) == 1
        assert rules[0].targets[0].directory == Path(r"C:\dest\A")
        assert rules[0].targets[0].suffix == "_magnate"

    def test_multiple_watch_sections_sorted_by_index(self, config_factory):
        """監視元は番号の昇順で取得される"""
        with config_factory("""
[Watch10]
processing_dir = C:\\src\\J
target_dir1 = C:\\dest\\J

[Watch2]
processing_dir = C:\\src\\B
target_dir1 = C:\\dest\\B

[Watch1]
processing_dir = C:\\src\\A
target_dir1 = C:\\dest\\A
"""):
            rules = get_watch_rules()

        assert [str(rule.source) for rule in rules] == [r"C:\src\A", r"C:\src\B", r"C:\src\J"]

    def test_targets_are_independent_per_watch(self, config_factory):
        """監視元ごとに独立した移動先ルールを持つ"""
        with config_factory("""
[Watch1]
processing_dir = C:\\src\\A
target_dir1 = C:\\dest\\A
filename1 = test1.md
pattern1 = _magnate

[Watch2]
processing_dir = C:\\src\\B
target_dir1 = C:\\dest\\B
filename1 = test2.txt
pattern1 = _backup
"""):
            rules = get_watch_rules()

        assert rules[0].targets[0].filenames == frozenset({"test1.md"})
        assert rules[0].targets[0].suffix == "_magnate"
        assert rules[1].targets[0].filenames == frozenset({"test2.txt"})
        assert rules[1].targets[0].suffix == "_backup"

    def test_no_watch_section_raises(self, config_factory):
        """Watchセクションが1つも無い場合はValueError"""
        with config_factory("""
[App]
wait_time = 0.5
"""):
            with pytest.raises(ValueError, match="監視ディレクトリ"):
                get_watch_rules()

    def test_unnumbered_watch_section_is_ignored(self, config_factory):
        """番号なしのWatchセクションは無視される"""
        with config_factory("""
[Watch]
processing_dir = C:\\src
target_dir1 = C:\\dest\\A
"""):
            with pytest.raises(ValueError, match="監視ディレクトリ"):
                get_watch_rules()

    def test_missing_processing_dir_raises(self, config_factory):
        """processing_dirが無い場合はValueError"""
        with config_factory("""
[Watch1]
target_dir1 = C:\\dest\\A
"""):
            with pytest.raises(ValueError, match="processing_dir"):
                get_watch_rules()


class TestGetWatchRulesTargets:
    """移動先ルールの解釈テスト"""

    def test_multiple_targets_sorted_by_index(self, config_factory):
        """移動先は番号の昇順で取得される"""
        with config_factory("""
[Watch1]
processing_dir = C:\\src
target_dir10 = C:\\dest\\J
filename10 =
target_dir2 = C:\\dest\\B
filename2 = test2.txt
target_dir1 = C:\\dest\\A
filename1 = test1.md
"""):
            rules = get_watch_rules()

        assert [str(target.directory) for target in rules[0].targets] == [
            r"C:\dest\A",
            r"C:\dest\B",
            r"C:\dest\J",
        ]

    def test_filenames_are_split_and_lowercased(self, config_factory):
        """カンマ区切りのファイル名が小文字化して分割される"""
        with config_factory("""
[Watch1]
processing_dir = C:\\src
target_dir1 = C:\\dest\\A
filename1 = Test1.MD , test2.txt,
"""):
            rules = get_watch_rules()

        assert rules[0].targets[0].filenames == frozenset({"test1.md", "test2.txt"})

    def test_empty_filename_matches_all_files(self, config_factory):
        """filenameが空欄の場合は全ファイルが対象"""
        with config_factory("""
[Watch1]
processing_dir = C:\\src
target_dir1 = C:\\dest\\A
filename1 =
"""):
            rules = get_watch_rules()

        assert rules[0].targets[0].filenames == frozenset()

    def test_pattern_per_target(self, config_factory):
        """ターゲットごとに異なるパターンを持つ"""
        with config_factory("""
[Watch1]
processing_dir = C:\\src
target_dir1 = C:\\dest\\A
pattern1 = _magnate
target_dir2 = C:\\dest\\B
pattern2 = _backup
"""):
            rules = get_watch_rules()

        assert rules[0].targets[0].suffix == "_magnate"
        assert rules[0].targets[1].suffix == "_backup"

    def test_empty_pattern_yields_no_pattern(self, config_factory):
        """patternが空欄の場合はサフィックスを追加しない"""
        with config_factory("""
[Watch1]
processing_dir = C:\\src
target_dir1 = C:\\dest\\A
pattern1 =
"""):
            rules = get_watch_rules()

        assert rules[0].targets[0].suffix == ""
        assert rules[0].targets[0].pattern is None

    def test_missing_pattern_key_yields_no_pattern(self, config_factory):
        """patternN自体が無い場合もサフィックスを追加しない"""
        with config_factory("""
[Watch1]
processing_dir = C:\\src
target_dir1 = C:\\dest\\A
pattern2 = _magnate
"""):
            rules = get_watch_rules()

        assert rules[0].targets[0].pattern is None

    def test_pattern_with_trailing_dollar(self, config_factory):
        """末尾の$はサフィックスから除去される"""
        with config_factory("""
[Watch1]
processing_dir = C:\\src
target_dir1 = C:\\dest\\A
pattern1 = _magnate$
"""):
            rules = get_watch_rules()

        assert rules[0].targets[0].suffix == "_magnate"
        assert rules[0].targets[0].pattern is not None
        assert rules[0].targets[0].pattern.pattern == "_magnate$"

    def test_no_target_dir_raises(self, config_factory):
        """target_dirNが1つも無い場合はValueError"""
        with config_factory("""
[Watch1]
processing_dir = C:\\src
"""):
            with pytest.raises(ValueError, match="移動先ディレクトリ"):
                get_watch_rules()

    def test_unnumbered_target_dir_is_ignored(self, config_factory):
        """番号なしのtarget_dirは無視される"""
        with config_factory("""
[Watch1]
processing_dir = C:\\src
target_dir = C:\\dest\\old
"""):
            with pytest.raises(ValueError, match="移動先ディレクトリ"):
                get_watch_rules()

    def test_invalid_pattern_raises(self, config_factory):
        """不正な正規表現はエラー"""
        import re

        with config_factory("""
[Watch1]
processing_dir = C:\\src
target_dir1 = C:\\dest\\A
pattern1 = [invalid
"""):
            with pytest.raises(re.error):
                get_watch_rules()
