import ctypes
import logging
import re
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, call, mock_open, patch

import pytest
from watchdog.events import FileCreatedEvent, FileMovedEvent

from service.file_rename_handler import FileRenameHandler, refresh_windows_folder


@pytest.fixture
def mock_config():
    """設定のモックを提供"""
    patterns = [re.compile(r'_renamed$')]
    with patch('service.file_rename_handler.get_rename_patterns') as mock_patterns, \
         patch('service.file_rename_handler.get_target_dir') as mock_target, \
         patch('service.file_rename_handler.get_wait_time') as mock_wait:
        mock_patterns.return_value = patterns
        mock_target.return_value = r'C:\test\target'
        mock_wait.return_value = 0.1
        yield {
            'patterns': mock_patterns,
            'target_dir': mock_target,
            'wait_time': mock_wait
        }


@pytest.fixture
def temp_test_dirs(tmp_path):
    """テスト用の一時ディレクトリを提供"""
    src_dir = tmp_path / 'src'
    target_dir = tmp_path / 'target'
    src_dir.mkdir()
    target_dir.mkdir()
    return {'src': src_dir, 'target': target_dir}


class TestRefreshWindowsFolder:
    """refresh_windows_folder関数のテスト"""

    def test_refresh_windows_folder_success(self):
        """正常にSHChangeNotifyを呼び出す"""
        with patch('ctypes.windll.shell32.SHChangeNotify') as mock_notify:
            refresh_windows_folder(r'C:\test\folder')
            mock_notify.assert_called_once()
            args = mock_notify.call_args[0]
            assert args[0] == 0x00001000  # SHCNE_UPDATEDIR
            assert args[1] == 0x0005      # SHCNF_PATHW
            assert args[2] == r'C:\test\folder'
            assert args[3] is None

    def test_refresh_windows_folder_handles_exception(self, caplog):
        """例外が発生してもログ出力のみで続行"""
        with patch('ctypes.windll.shell32.SHChangeNotify', side_effect=Exception('Test error')):
            with caplog.at_level(logging.DEBUG):
                refresh_windows_folder(r'C:\test\folder')
            assert "フォルダ更新通知に失敗しました" in caplog.text


class TestFileRenameHandlerInit:
    """FileRenameHandlerの初期化テスト"""

    def test_init_success(self, mock_config):
        """正常な初期化"""
        with patch.object(Path, 'exists', return_value=True):
            handler = FileRenameHandler()
            assert handler.patterns == [re.compile(r'_renamed$')]
            assert handler.wait_time == 0.1
            assert str(handler.target_dir) == r'C:\test\target'

    def test_init_creates_target_dir_if_not_exists(self, mock_config, caplog):
        """移動先ディレクトリが存在しない場合は作成"""
        with patch.object(Path, 'exists', return_value=False), \
             patch.object(Path, 'mkdir') as mock_mkdir:
            with caplog.at_level(logging.INFO):
                handler = FileRenameHandler()
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
            assert "移動先ディレクトリを作成しました" in caplog.text

    def test_ensure_target_dir_called_on_init(self, mock_config):
        """初期化時にtarget_dirの確認が呼ばれる"""
        with patch.object(FileRenameHandler, '_ensure_target_dir') as mock_ensure:
            handler = FileRenameHandler()
            mock_ensure.assert_called_once()


class TestFileRenameHandlerWaitForFileReady:
    """_wait_for_file_readyメソッドのテスト"""

    def test_wait_for_file_ready_success(self, mock_config, temp_test_dirs):
        """ファイルが準備完了で正常終了"""
        handler = FileRenameHandler()
        handler.wait_time = 0.01  # テスト高速化
        test_file = temp_test_dirs['src'] / 'test.txt'
        test_file.write_text('test content')

        result = handler._wait_for_file_ready(test_file)
        assert result is True

    def test_wait_for_file_ready_file_not_exists(self, mock_config):
        """ファイルが存在しない場合はFalse"""
        handler = FileRenameHandler()
        handler.wait_time = 0.01
        non_existent = Path(r'C:\test\nonexistent.txt')

        with patch.object(Path, 'exists', return_value=False):
            result = handler._wait_for_file_ready(non_existent)
        assert result is False

    def test_wait_for_file_ready_file_locked(self, mock_config):
        """ファイルがロックされている場合の再試行"""
        handler = FileRenameHandler()
        handler.wait_time = 0.01
        test_file = Path(r'C:\test\locked.txt')

        # 最初の2回はPermissionError、3回目は成功
        open_mock = mock_open()
        open_mock.side_effect = [PermissionError(), PermissionError(), mock_open()()]

        with patch.object(Path, 'exists', return_value=True), \
             patch('builtins.open', open_mock):
            result = handler._wait_for_file_ready(test_file, max_retries=3)

        # 3回試行される
        assert open_mock.call_count == 3
        assert result is True

    def test_wait_for_file_ready_max_retries_exceeded(self, mock_config):
        """最大再試行回数を超えた場合はFalse"""
        handler = FileRenameHandler()
        handler.wait_time = 0.01
        test_file = Path(r'C:\test\locked.txt')

        open_mock = mock_open()
        open_mock.side_effect = PermissionError()

        with patch.object(Path, 'exists', return_value=True), \
             patch('builtins.open', open_mock):
            result = handler._wait_for_file_ready(test_file, max_retries=3)

        assert result is False


class TestFileRenameHandlerHasPattern:
    """_has_patternメソッドのテスト"""

    def test_has_pattern_true(self, mock_config):
        """パターンが存在する場合"""
        handler = FileRenameHandler()
        result = handler._has_pattern('myfile_renamed')
        assert result is True

    def test_has_pattern_false(self, mock_config):
        """パターンが存在しない場合"""
        handler = FileRenameHandler()
        result = handler._has_pattern('myfile')
        assert result is False

    def test_has_pattern_multiple_patterns(self, mock_config):
        """複数パターンのチェック"""
        patterns = [re.compile(r'_renamed$'), re.compile(r'_processed$')]
        mock_config['patterns'].return_value = patterns
        handler = FileRenameHandler()
        handler.patterns = patterns

        assert handler._has_pattern('file_renamed') is True
        assert handler._has_pattern('file_processed') is True
        assert handler._has_pattern('file_other') is False


class TestFileRenameHandlerOnCreated:
    """on_createdメソッドのテスト"""

    def test_on_created_processes_file(self, mock_config):
        """ファイル作成イベントを処理"""
        handler = FileRenameHandler()
        event = FileCreatedEvent(r'C:\test\src\newfile.txt')

        with patch.object(handler, '_process_file') as mock_process:
            handler.on_created(event)
            mock_process.assert_called_once_with(r'C:\test\src\newfile.txt')

    def test_on_created_ignores_directory(self, mock_config):
        """ディレクトリ作成イベントは無視"""
        handler = FileRenameHandler()
        event = FileCreatedEvent(r'C:\test\src\newdir')
        event.is_directory = True

        with patch.object(handler, '_process_file') as mock_process:
            handler.on_created(event)
            mock_process.assert_not_called()


class TestFileRenameHandlerOnMoved:
    """on_movedメソッドのテスト"""

    def test_on_moved_processes_file(self, mock_config):
        """ファイル移動イベントを処理"""
        handler = FileRenameHandler()
        event = FileMovedEvent(r'C:\test\src\old.txt', r'C:\test\src\new.txt')

        with patch.object(handler, '_process_file') as mock_process:
            handler.on_moved(event)
            mock_process.assert_called_once_with(r'C:\test\src\new.txt')

    def test_on_moved_ignores_directory(self, mock_config):
        """ディレクトリ移動イベントは無視"""
        handler = FileRenameHandler()
        event = FileMovedEvent(r'C:\test\src\olddir', r'C:\test\src\newdir')
        event.is_directory = True

        with patch.object(handler, '_process_file') as mock_process:
            handler.on_moved(event)
            mock_process.assert_not_called()


class TestFileRenameHandlerProcessFile:
    """_process_fileメソッドのテスト"""

    def test_process_file_waits_for_ready(self, mock_config, temp_test_dirs):
        """ファイルの準備を待つ"""
        handler = FileRenameHandler()
        test_file = temp_test_dirs['src'] / 'test.txt'
        test_file.write_text('content')

        with patch.object(handler, '_wait_for_file_ready', return_value=True) as mock_wait, \
             patch.object(handler, '_has_pattern', return_value=False), \
             patch.object(handler, '_rename_and_move_file') as mock_rename:
            handler._process_file(str(test_file))
            mock_wait.assert_called_once()

    def test_process_file_not_ready_logs_warning(self, mock_config, caplog):
        """ファイルの準備ができない場合は警告ログ"""
        handler = FileRenameHandler()
        test_file = Path(r'C:\test\src\test.txt')

        with patch.object(handler, '_wait_for_file_ready', return_value=False):
            with caplog.at_level(logging.WARNING):
                handler._process_file(str(test_file))
            assert "ファイルの準備ができませんでした" in caplog.text

    def test_process_file_with_existing_pattern_moves_only(self, mock_config, temp_test_dirs):
        """既にパターンがある場合はリネームせず移動のみ"""
        handler = FileRenameHandler()
        test_file = temp_test_dirs['src'] / 'file_renamed.txt'
        test_file.write_text('content')

        with patch.object(handler, '_wait_for_file_ready', return_value=True), \
             patch.object(handler, '_has_pattern', return_value=True), \
             patch.object(handler, '_move_file') as mock_move, \
             patch.object(handler, '_rename_and_move_file') as mock_rename:
            handler._process_file(str(test_file))
            mock_move.assert_called_once()
            mock_rename.assert_not_called()

    def test_process_file_without_pattern_renames_and_moves(self, mock_config, temp_test_dirs):
        """パターンがない場合はリネームして移動"""
        handler = FileRenameHandler()
        test_file = temp_test_dirs['src'] / 'file.txt'
        test_file.write_text('content')

        with patch.object(handler, '_wait_for_file_ready', return_value=True), \
             patch.object(handler, '_has_pattern', return_value=False), \
             patch.object(handler, '_rename_and_move_file') as mock_rename, \
             patch.object(handler, '_move_file') as mock_move:
            handler._process_file(str(test_file))
            mock_rename.assert_called_once()
            mock_move.assert_not_called()

    def test_process_file_returns_if_file_not_exists_after_wait(self, mock_config):
        """待機後にファイルが存在しない場合は何もしない"""
        handler = FileRenameHandler()
        test_file = Path(r'C:\test\src\test.txt')

        with patch.object(handler, '_wait_for_file_ready', return_value=True), \
             patch.object(Path, 'exists', return_value=False), \
             patch.object(handler, '_has_pattern') as mock_has, \
             patch.object(handler, '_rename_and_move_file') as mock_rename:
            handler._process_file(str(test_file))
            mock_has.assert_not_called()
            mock_rename.assert_not_called()


class TestFileRenameHandlerRenameAndMoveFile:
    """_rename_and_move_fileメソッドのテスト"""

    def test_rename_and_move_file_success(self, mock_config, temp_test_dirs, caplog):
        """ファイルを正しくリネームして移動"""
        handler = FileRenameHandler()
        handler.target_dir = temp_test_dirs['target']
        test_file = temp_test_dirs['src'] / 'original.txt'
        test_file.write_text('content')

        with patch('service.file_rename_handler.refresh_windows_folder') as mock_refresh:
            with caplog.at_level(logging.INFO):
                handler._rename_and_move_file(test_file, 'original', '.txt')

        new_file = temp_test_dirs['target'] / 'original_renamed.txt'
        assert new_file.exists()
        assert not test_file.exists()
        assert "ファイルをリネーム＆移動しました" in caplog.text
        # refresh_windows_folderが2回呼ばれる（ソースとターゲット）
        assert mock_refresh.call_count == 2

    def test_rename_and_move_file_overwrites_existing(self, mock_config, temp_test_dirs, caplog):
        """既存ファイルを上書き"""
        handler = FileRenameHandler()
        handler.target_dir = temp_test_dirs['target']
        test_file = temp_test_dirs['src'] / 'file.txt'
        test_file.write_text('new content')
        existing_file = temp_test_dirs['target'] / 'file_renamed.txt'
        existing_file.write_text('old content')

        with patch('service.file_rename_handler.refresh_windows_folder'):
            with caplog.at_level(logging.INFO):
                handler._rename_and_move_file(test_file, 'file', '.txt')

        new_file = temp_test_dirs['target'] / 'file_renamed.txt'
        assert new_file.read_text() == 'new content'
        assert "既存ファイルを上書きします" in caplog.text

    def test_rename_and_move_file_no_patterns(self, mock_config, temp_test_dirs, caplog):
        """パターンが設定されていない場合は移動のみ"""
        mock_config['patterns'].return_value = []
        handler = FileRenameHandler()
        handler.patterns = []
        handler.target_dir = temp_test_dirs['target']
        test_file = temp_test_dirs['src'] / 'file.txt'
        test_file.write_text('content')

        with patch.object(handler, '_move_file') as mock_move:
            with caplog.at_level(logging.WARNING):
                handler._rename_and_move_file(test_file, 'file', '.txt')
            mock_move.assert_called_once_with(test_file)
            assert "リネームパターンが設定されていません" in caplog.text

    def test_rename_and_move_file_handles_exception(self, mock_config, temp_test_dirs, caplog):
        """移動時の例外を処理"""
        handler = FileRenameHandler()
        handler.target_dir = temp_test_dirs['target']
        test_file = temp_test_dirs['src'] / 'file.txt'
        test_file.write_text('content')

        with patch('shutil.move', side_effect=Exception('Test error')):
            with caplog.at_level(logging.ERROR):
                handler._rename_and_move_file(test_file, 'file', '.txt')
            assert "ファイルの移動に失敗しました" in caplog.text


class TestFileRenameHandlerMoveFile:
    """_move_fileメソッドのテスト"""

    def test_move_file_success(self, mock_config, temp_test_dirs, caplog):
        """ファイルを正しく移動"""
        handler = FileRenameHandler()
        handler.target_dir = temp_test_dirs['target']
        test_file = temp_test_dirs['src'] / 'file.txt'
        test_file.write_text('content')

        with patch('service.file_rename_handler.refresh_windows_folder') as mock_refresh:
            with caplog.at_level(logging.INFO):
                handler._move_file(test_file)

        new_file = temp_test_dirs['target'] / 'file.txt'
        assert new_file.exists()
        assert not test_file.exists()
        assert "ファイルを移動しました" in caplog.text
        assert mock_refresh.call_count == 2

    def test_move_file_overwrites_existing(self, mock_config, temp_test_dirs, caplog):
        """既存ファイルを上書き"""
        handler = FileRenameHandler()
        handler.target_dir = temp_test_dirs['target']
        test_file = temp_test_dirs['src'] / 'file.txt'
        test_file.write_text('new content')
        existing_file = temp_test_dirs['target'] / 'file.txt'
        existing_file.write_text('old content')

        with patch('service.file_rename_handler.refresh_windows_folder'):
            with caplog.at_level(logging.INFO):
                handler._move_file(test_file)

        new_file = temp_test_dirs['target'] / 'file.txt'
        assert new_file.read_text() == 'new content'
        assert "既存ファイルを上書きします" in caplog.text

    def test_move_file_handles_exception(self, mock_config, temp_test_dirs, caplog):
        """移動時の例外を処理"""
        handler = FileRenameHandler()
        handler.target_dir = temp_test_dirs['target']
        test_file = temp_test_dirs['src'] / 'file.txt'
        test_file.write_text('content')

        with patch('shutil.move', side_effect=Exception('Test error')):
            with caplog.at_level(logging.ERROR):
                handler._move_file(test_file)
            assert "ファイルの移動に失敗しました" in caplog.text
