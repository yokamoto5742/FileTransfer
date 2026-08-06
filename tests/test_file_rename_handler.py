import logging
import re
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
from watchdog.events import FileCreatedEvent, FileMovedEvent

from service.file_rename_handler import FileRenameHandler, refresh_windows_folder
from utils.config_manager import TargetRule


def make_rule(directory, filenames=(), suffix="_renamed") -> TargetRule:
    """テスト用のTargetRuleを生成"""
    return TargetRule(
        directory=Path(directory),
        filenames=frozenset(name.lower() for name in filenames),
        suffix=suffix,
        pattern=re.compile(f"{suffix}$") if suffix else None,
    )


@pytest.fixture
def mock_config():
    """設定のモックを提供"""
    rules = [make_rule(r"C:\test\target")]
    with (
        patch("service.file_rename_handler.get_target_rules") as mock_rules,
        patch("service.file_rename_handler.get_wait_time") as mock_wait,
    ):
        mock_rules.return_value = rules
        mock_wait.return_value = 0.1
        yield {"rules": mock_rules, "wait_time": mock_wait}


@pytest.fixture
def temp_test_dirs(tmp_path):
    """テスト用の一時ディレクトリを提供"""
    src_dir = tmp_path / "src"
    target_dir = tmp_path / "target"
    other_dir = tmp_path / "other"
    src_dir.mkdir()
    target_dir.mkdir()
    other_dir.mkdir()
    return {"src": src_dir, "target": target_dir, "other": other_dir}


class TestRefreshWindowsFolder:
    """refresh_windows_folder関数のテスト"""

    def test_refresh_windows_folder_success(self):
        """正常にSHChangeNotifyを呼び出す"""
        with patch("ctypes.windll.shell32.SHChangeNotify") as mock_notify:
            refresh_windows_folder(r"C:\test\folder")
            mock_notify.assert_called_once()
            args = mock_notify.call_args[0]
            assert args[0] == 0x00001000  # SHCNE_UPDATEDIR
            assert args[1] == 0x0005  # SHCNF_PATHW
            assert args[2] == r"C:\test\folder"
            assert args[3] is None

    def test_refresh_windows_folder_handles_exception(self, caplog):
        """例外が発生してもログ出力のみで続行"""
        with patch("ctypes.windll.shell32.SHChangeNotify", side_effect=Exception("Test error")):
            with caplog.at_level(logging.DEBUG):
                refresh_windows_folder(r"C:\test\folder")
            assert "フォルダ更新通知に失敗しました" in caplog.text


class TestFileRenameHandlerInit:
    """FileRenameHandlerの初期化テスト"""

    def test_init_success(self, mock_config):
        """正常な初期化"""
        with patch.object(Path, "exists", return_value=True):
            handler = FileRenameHandler()
            assert len(handler.rules) == 1
            assert handler.wait_time == 0.1
            assert str(handler.rules[0].directory) == r"C:\test\target"

    def test_init_creates_target_dirs_if_not_exists(self, mock_config, caplog):
        """移動先ディレクトリが存在しない場合は作成"""
        with (
            patch.object(Path, "exists", return_value=False),
            patch.object(Path, "mkdir") as mock_mkdir,
        ):
            with caplog.at_level(logging.INFO):
                FileRenameHandler()
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
            assert "移動先ディレクトリを作成しました" in caplog.text

    def test_init_creates_all_target_dirs(self, mock_config):
        """複数の移動先ディレクトリをすべて作成"""
        mock_config["rules"].return_value = [
            make_rule(r"C:\test\a"),
            make_rule(r"C:\test\b"),
        ]
        with (
            patch.object(Path, "exists", return_value=False),
            patch.object(Path, "mkdir") as mock_mkdir,
        ):
            FileRenameHandler()
            assert mock_mkdir.call_count == 2

    def test_ensure_target_dirs_called_on_init(self, mock_config):
        """初期化時に移動先ディレクトリの確認が呼ばれる"""
        with patch.object(FileRenameHandler, "_ensure_target_dirs") as mock_ensure:
            FileRenameHandler()
            mock_ensure.assert_called_once()


class TestFileRenameHandlerWaitForFileReady:
    """_wait_for_file_readyメソッドのテスト"""

    def test_wait_for_file_ready_success(self, mock_config, temp_test_dirs):
        """ファイルが準備完了で正常終了"""
        handler = FileRenameHandler()
        handler.wait_time = 0.01  # テスト高速化
        test_file = temp_test_dirs["src"] / "test.txt"
        test_file.write_text("test content")

        result = handler._wait_for_file_ready(test_file)
        assert result is True

    def test_wait_for_file_ready_file_not_exists(self, mock_config):
        """ファイルが存在しない場合はFalse"""
        handler = FileRenameHandler()
        handler.wait_time = 0.01
        non_existent = Path(r"C:\test\nonexistent.txt")

        with patch.object(Path, "exists", return_value=False):
            result = handler._wait_for_file_ready(non_existent)
        assert result is False

    def test_wait_for_file_ready_file_locked(self, mock_config):
        """ファイルがロックされている場合の再試行"""
        handler = FileRenameHandler()
        handler.wait_time = 0.01
        test_file = Path(r"C:\test\locked.txt")

        # 最初の2回はPermissionError、3回目は成功
        open_mock = mock_open()
        open_mock.side_effect = [PermissionError(), PermissionError(), mock_open()()]

        with patch.object(Path, "exists", return_value=True), patch("builtins.open", open_mock):
            result = handler._wait_for_file_ready(test_file, max_retries=3)

        # 3回試行される
        assert open_mock.call_count == 3
        assert result is True

    def test_wait_for_file_ready_max_retries_exceeded(self, mock_config):
        """最大再試行回数を超えた場合はFalse"""
        handler = FileRenameHandler()
        handler.wait_time = 0.01
        test_file = Path(r"C:\test\locked.txt")

        open_mock = mock_open()
        open_mock.side_effect = PermissionError()

        with patch.object(Path, "exists", return_value=True), patch("builtins.open", open_mock):
            result = handler._wait_for_file_ready(test_file, max_retries=3)

        assert result is False


class TestFileRenameHandlerResolveRule:
    """_resolve_ruleメソッドのテスト"""

    def test_resolve_rule_prefers_filename_match(self, mock_config):
        """ファイル名指定のあるルールを優先する"""
        mock_config["rules"].return_value = [
            make_rule(r"C:\test\all"),
            make_rule(r"C:\test\specific", filenames=["test1.md"]),
        ]
        handler = FileRenameHandler()

        rule = handler._resolve_rule("test1.md")
        assert rule is not None
        assert str(rule.directory) == r"C:\test\specific"

    def test_resolve_rule_is_case_insensitive(self, mock_config):
        """ファイル名の一致判定は大文字小文字を区別しない"""
        mock_config["rules"].return_value = [
            make_rule(r"C:\test\specific", filenames=["test1.md"]),
        ]
        handler = FileRenameHandler()

        rule = handler._resolve_rule("TEST1.MD")
        assert rule is not None
        assert str(rule.directory) == r"C:\test\specific"

    def test_resolve_rule_falls_back_to_empty_filenames(self, mock_config):
        """指定に一致しない場合はファイル名指定なしのルールへ"""
        mock_config["rules"].return_value = [
            make_rule(r"C:\test\specific", filenames=["test1.md"]),
            make_rule(r"C:\test\all"),
        ]
        handler = FileRenameHandler()

        rule = handler._resolve_rule("other.txt")
        assert rule is not None
        assert str(rule.directory) == r"C:\test\all"

    def test_resolve_rule_returns_none_without_catch_all(self, mock_config):
        """一致するルールも受け皿もない場合はNone"""
        mock_config["rules"].return_value = [
            make_rule(r"C:\test\specific", filenames=["test1.md"]),
        ]
        handler = FileRenameHandler()

        assert handler._resolve_rule("other.txt") is None

    def test_resolve_rule_uses_first_matching_rule(self, mock_config):
        """同じファイル名が複数のルールにある場合は先頭のルール"""
        mock_config["rules"].return_value = [
            make_rule(r"C:\test\first", filenames=["test1.md"]),
            make_rule(r"C:\test\second", filenames=["test1.md"]),
        ]
        handler = FileRenameHandler()

        rule = handler._resolve_rule("test1.md")
        assert rule is not None
        assert str(rule.directory) == r"C:\test\first"


class TestFileRenameHandlerBuildTargetName:
    """_build_target_nameメソッドのテスト"""

    def test_build_target_name_adds_suffix(self, mock_config):
        """サフィックスが付いていない場合は追加"""
        handler = FileRenameHandler()
        rule = make_rule(r"C:\test\target")

        assert handler._build_target_name(Path("file.txt"), rule) == "file_renamed.txt"

    def test_build_target_name_keeps_existing_suffix(self, mock_config):
        """既にサフィックスが付いている場合はそのまま"""
        handler = FileRenameHandler()
        rule = make_rule(r"C:\test\target")

        assert handler._build_target_name(Path("file_renamed.txt"), rule) == "file_renamed.txt"

    def test_build_target_name_without_pattern(self, mock_config):
        """パターンが未設定の場合は何も追加しない"""
        handler = FileRenameHandler()
        rule = make_rule(r"C:\test\target", suffix="")

        assert handler._build_target_name(Path("file.txt"), rule) == "file.txt"

    def test_build_target_name_uses_rule_specific_suffix(self, mock_config):
        """ターゲットごとのサフィックスが使われる"""
        handler = FileRenameHandler()
        rule = make_rule(r"C:\test\target", suffix="_backup")

        assert handler._build_target_name(Path("file.txt"), rule) == "file_backup.txt"


class TestFileRenameHandlerOnCreated:
    """on_createdメソッドのテスト"""

    def test_on_created_processes_file(self, mock_config):
        """ファイル作成イベントを処理"""
        handler = FileRenameHandler()
        event = FileCreatedEvent(r"C:\test\src\newfile.txt")

        with patch.object(handler, "_process_file") as mock_process:
            handler.on_created(event)
            mock_process.assert_called_once_with(r"C:\test\src\newfile.txt")

    def test_on_created_ignores_directory(self, mock_config):
        """ディレクトリ作成イベントは無視"""
        handler = FileRenameHandler()
        event = FileCreatedEvent(r"C:\test\src\newdir")
        event.is_directory = True

        with patch.object(handler, "_process_file") as mock_process:
            handler.on_created(event)
            mock_process.assert_not_called()


class TestFileRenameHandlerOnMoved:
    """on_movedメソッドのテスト"""

    def test_on_moved_processes_file(self, mock_config):
        """ファイル移動イベントを処理"""
        handler = FileRenameHandler()
        event = FileMovedEvent(r"C:\test\src\old.txt", r"C:\test\src\new.txt")

        with patch.object(handler, "_process_file") as mock_process:
            handler.on_moved(event)
            mock_process.assert_called_once_with(r"C:\test\src\new.txt")

    def test_on_moved_ignores_directory(self, mock_config):
        """ディレクトリ移動イベントは無視"""
        handler = FileRenameHandler()
        event = FileMovedEvent(r"C:\test\src\olddir", r"C:\test\src\newdir")
        event.is_directory = True

        with patch.object(handler, "_process_file") as mock_process:
            handler.on_moved(event)
            mock_process.assert_not_called()


class TestFileRenameHandlerProcessFile:
    """_process_fileメソッドのテスト"""

    def test_process_file_waits_for_ready(self, mock_config, temp_test_dirs):
        """ファイルの準備を待つ"""
        handler = FileRenameHandler()
        test_file = temp_test_dirs["src"] / "test.txt"
        test_file.write_text("content")

        with (
            patch.object(handler, "_wait_for_file_ready", return_value=True) as mock_wait,
            patch.object(handler, "_move_file"),
        ):
            handler._process_file(str(test_file))
            mock_wait.assert_called_once()

    def test_process_file_not_ready_logs_warning(self, mock_config, caplog):
        """ファイルの準備ができない場合は警告ログ"""
        handler = FileRenameHandler()
        test_file = Path(r"C:\test\src\test.txt")

        with patch.object(handler, "_wait_for_file_ready", return_value=False):
            with caplog.at_level(logging.WARNING):
                handler._process_file(str(test_file))
            assert "ファイルの準備ができませんでした" in caplog.text

    def test_process_file_returns_if_file_not_exists_after_wait(self, mock_config):
        """待機後にファイルが存在しない場合は何もしない"""
        handler = FileRenameHandler()
        test_file = Path(r"C:\test\src\test.txt")

        with (
            patch.object(handler, "_wait_for_file_ready", return_value=True),
            patch.object(Path, "exists", return_value=False),
            patch.object(handler, "_move_file") as mock_move,
        ):
            handler._process_file(str(test_file))
            mock_move.assert_not_called()

    def test_process_file_moves_to_matching_target(self, mock_config, temp_test_dirs):
        """ファイル名指定に一致するターゲットへ移動"""
        mock_config["rules"].return_value = [
            make_rule(temp_test_dirs["target"]),
            make_rule(temp_test_dirs["other"], filenames=["test1.md"], suffix=""),
        ]
        handler = FileRenameHandler()
        test_file = temp_test_dirs["src"] / "test1.md"
        test_file.write_text("content")

        with (
            patch.object(handler, "_wait_for_file_ready", return_value=True),
            patch("service.file_rename_handler.refresh_windows_folder"),
        ):
            handler._process_file(str(test_file))

        assert (temp_test_dirs["other"] / "test1.md").exists()
        assert not test_file.exists()

    def test_process_file_matches_ignoring_case(self, mock_config, temp_test_dirs):
        """大文字小文字が違っても一致する"""
        mock_config["rules"].return_value = [
            make_rule(temp_test_dirs["other"], filenames=["test1.md"], suffix=""),
        ]
        handler = FileRenameHandler()
        test_file = temp_test_dirs["src"] / "TEST1.MD"
        test_file.write_text("content")

        with (
            patch.object(handler, "_wait_for_file_ready", return_value=True),
            patch("service.file_rename_handler.refresh_windows_folder"),
        ):
            handler._process_file(str(test_file))

        assert (temp_test_dirs["other"] / "TEST1.MD").exists()

    def test_process_file_moves_unmatched_to_catch_all(self, mock_config, temp_test_dirs):
        """指定に一致しないファイルは受け皿ターゲットへ"""
        mock_config["rules"].return_value = [
            make_rule(temp_test_dirs["other"], filenames=["test1.md"]),
            make_rule(temp_test_dirs["target"], suffix=""),
        ]
        handler = FileRenameHandler()
        test_file = temp_test_dirs["src"] / "other.txt"
        test_file.write_text("content")

        with (
            patch.object(handler, "_wait_for_file_ready", return_value=True),
            patch("service.file_rename_handler.refresh_windows_folder"),
        ):
            handler._process_file(str(test_file))

        assert (temp_test_dirs["target"] / "other.txt").exists()

    def test_process_file_keeps_file_without_matching_target(
        self, mock_config, temp_test_dirs, caplog
    ):
        """移動先が無い場合はファイルを残してログ出力"""
        mock_config["rules"].return_value = [
            make_rule(temp_test_dirs["other"], filenames=["test1.md"]),
        ]
        handler = FileRenameHandler()
        test_file = temp_test_dirs["src"] / "other.txt"
        test_file.write_text("content")

        with patch.object(handler, "_wait_for_file_ready", return_value=True):
            with caplog.at_level(logging.INFO):
                handler._process_file(str(test_file))

        assert test_file.exists()
        assert "移動先が見つかりませんでした" in caplog.text

    def test_process_file_applies_target_specific_pattern(self, mock_config, temp_test_dirs):
        """ターゲットごとに異なるパターンが適用される"""
        mock_config["rules"].return_value = [
            make_rule(temp_test_dirs["other"], filenames=["test1.md"], suffix="_backup"),
            make_rule(temp_test_dirs["target"], suffix="_magnate"),
        ]
        handler = FileRenameHandler()
        matched_file = temp_test_dirs["src"] / "test1.md"
        matched_file.write_text("content")
        other_file = temp_test_dirs["src"] / "other.txt"
        other_file.write_text("content")

        with (
            patch.object(handler, "_wait_for_file_ready", return_value=True),
            patch("service.file_rename_handler.refresh_windows_folder"),
        ):
            handler._process_file(str(matched_file))
            handler._process_file(str(other_file))

        assert (temp_test_dirs["other"] / "test1_backup.md").exists()
        assert (temp_test_dirs["target"] / "other_magnate.txt").exists()


class TestFileRenameHandlerMoveFile:
    """_move_fileメソッドのテスト"""

    def test_move_file_renames_and_moves(self, mock_config, temp_test_dirs, caplog):
        """ファイルを正しくリネームして移動"""
        handler = FileRenameHandler()
        rule = make_rule(temp_test_dirs["target"])
        test_file = temp_test_dirs["src"] / "original.txt"
        test_file.write_text("content")

        with patch("service.file_rename_handler.refresh_windows_folder") as mock_refresh:
            with caplog.at_level(logging.INFO):
                handler._move_file(test_file, rule)

        assert (temp_test_dirs["target"] / "original_renamed.txt").exists()
        assert not test_file.exists()
        assert "ファイルを移動しました" in caplog.text
        # refresh_windows_folderが2回呼ばれる（ソースとターゲット）
        assert mock_refresh.call_count == 2

    def test_move_file_without_pattern(self, mock_config, temp_test_dirs):
        """パターンが未設定の場合はリネームせず移動"""
        handler = FileRenameHandler()
        rule = make_rule(temp_test_dirs["target"], suffix="")
        test_file = temp_test_dirs["src"] / "file.txt"
        test_file.write_text("content")

        with patch("service.file_rename_handler.refresh_windows_folder"):
            handler._move_file(test_file, rule)

        assert (temp_test_dirs["target"] / "file.txt").exists()

    def test_move_file_overwrites_existing(self, mock_config, temp_test_dirs, caplog):
        """既存ファイルを上書き"""
        handler = FileRenameHandler()
        rule = make_rule(temp_test_dirs["target"], suffix="")
        test_file = temp_test_dirs["src"] / "file.txt"
        test_file.write_text("new content")
        existing_file = temp_test_dirs["target"] / "file.txt"
        existing_file.write_text("old content")

        with patch("service.file_rename_handler.refresh_windows_folder"):
            with caplog.at_level(logging.INFO):
                handler._move_file(test_file, rule)

        assert existing_file.read_text() == "new content"
        assert "既存ファイルを上書きします" in caplog.text

    def test_move_file_handles_exception(self, mock_config, temp_test_dirs, caplog):
        """移動時の例外を処理"""
        handler = FileRenameHandler()
        rule = make_rule(temp_test_dirs["target"])
        test_file = temp_test_dirs["src"] / "file.txt"
        test_file.write_text("content")

        with patch("shutil.move", side_effect=Exception("Test error")):
            with caplog.at_level(logging.ERROR):
                handler._move_file(test_file, rule)
            assert "ファイルの移動に失敗しました" in caplog.text
