import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image
from watchdog.observers import Observer

from app.tray_app import TrayApp
from utils.config_manager import TargetRule, WatchRule


def make_watch_rule(source, targets=(r"C:\test\target",)) -> WatchRule:
    """テスト用のWatchRuleを生成"""
    return WatchRule(
        source=Path(source),
        targets=tuple(
            TargetRule(directory=Path(target), filenames=frozenset(), suffix="", pattern=None)
            for target in targets
        ),
    )


@pytest.fixture
def mock_config():
    """設定のモックを提供"""
    with (
        patch("app.tray_app.get_watch_rules") as mock_rules,
        patch("app.tray_app.get_wait_time") as mock_wait,
    ):
        mock_rules.return_value = [make_watch_rule(r"C:\test\src")]
        mock_wait.return_value = 0.5
        yield mock_rules


@pytest.fixture
def existing_dirs():
    """監視フォルダが存在する状態にする"""
    with patch.object(Path, "exists", return_value=True):
        yield


@pytest.fixture
def mock_observer():
    """Observerのモックを提供"""
    with patch("app.tray_app.Observer") as mock_obs:
        yield mock_obs


@pytest.fixture
def mock_pystray():
    """pystrayのモックを提供"""
    with patch("app.tray_app.pystray") as mock_ps:
        yield mock_ps


@pytest.fixture
def mock_subprocess():
    """subprocessのモックを提供"""
    with patch("app.tray_app.subprocess") as mock_sp:
        yield mock_sp


class TestTrayAppInit:
    """TrayAppの初期化テスト"""

    def test_init_success(self, mock_config, existing_dirs):
        """正常な初期化"""
        app = TrayApp()
        assert [str(rule.source) for rule in app.watch_rules] == [r"C:\test\src"]
        assert app.observer is None
        assert app.icon is None

    def test_init_keeps_multiple_watch_rules(self, mock_config, existing_dirs):
        """複数の監視フォルダを保持する"""
        mock_config.return_value = [
            make_watch_rule(r"C:\test\src1"),
            make_watch_rule(r"C:\test\src2", targets=(r"C:\test\target2",)),
        ]
        app = TrayApp()
        assert [str(rule.source) for rule in app.watch_rules] == [r"C:\test\src1", r"C:\test\src2"]

    def test_init_with_missing_src_dir(self, mock_config):
        """監視フォルダが存在しない場合はsys.exitを呼ぶ"""
        with patch.object(Path, "exists", return_value=False):
            with pytest.raises(SystemExit) as excinfo:
                TrayApp()
            assert excinfo.value.code == 1

    def test_validate_src_dir_logs_error(self, mock_config, caplog):
        """監視フォルダが存在しない場合のログ出力"""
        with patch.object(Path, "exists", return_value=False):
            with caplog.at_level(logging.ERROR):
                with pytest.raises(SystemExit):
                    TrayApp()
            assert "監視フォルダが存在しません" in caplog.text

    def test_init_skips_missing_src_dir(self, mock_config, caplog):
        """存在しない監視フォルダのみ除外し、残りで起動する"""
        mock_config.return_value = [
            make_watch_rule(r"C:\test\missing"),
            make_watch_rule(r"C:\test\src"),
        ]
        with patch.object(Path, "exists", side_effect=[False, True]):
            with caplog.at_level(logging.ERROR):
                app = TrayApp()

        assert [str(rule.source) for rule in app.watch_rules] == [r"C:\test\src"]
        assert "監視フォルダが存在しません" in caplog.text


class TestTrayAppMoveLoop:
    """移動ループ検出のテスト"""

    def test_target_same_as_own_source_exits(self, mock_config, existing_dirs, caplog):
        """移動先が自身の監視フォルダと同一の場合は終了"""
        mock_config.return_value = [make_watch_rule(r"C:\test\src", targets=(r"C:\test\src",))]

        with caplog.at_level(logging.ERROR):
            with pytest.raises(SystemExit) as excinfo:
                TrayApp()

        assert excinfo.value.code == 1
        assert "移動先が監視フォルダと同一です" in caplog.text

    def test_target_same_as_other_source_exits(self, mock_config, existing_dirs, caplog):
        """移動先が別の監視フォルダと同一の場合も終了"""
        mock_config.return_value = [
            make_watch_rule(r"C:\test\src1", targets=(r"C:\test\src2",)),
            make_watch_rule(r"C:\test\src2", targets=(r"C:\test\target",)),
        ]

        with caplog.at_level(logging.ERROR):
            with pytest.raises(SystemExit):
                TrayApp()

        assert "移動先が監視フォルダと同一です" in caplog.text

    def test_target_under_source_is_allowed(self, mock_config, existing_dirs):
        """移動先が監視フォルダ配下の場合はrecursive=Falseのため許容する"""
        mock_config.return_value = [make_watch_rule(r"C:\test\src", targets=(r"C:\test\src\done",))]

        app = TrayApp()
        assert len(app.watch_rules) == 1


class TestTrayAppIconCreation:
    """アイコン作成のテスト"""

    def test_create_icon_image_returns_pil_image(self, mock_config, existing_dirs):
        """アイコン画像が正しく作成される"""
        app = TrayApp()
        image = app._create_icon_image()
        assert isinstance(image, Image.Image)
        assert image.size == (64, 64)
        assert image.mode == "RGBA"


class TestTrayAppFolderOperations:
    """フォルダ操作のテスト"""

    def test_open_folder_calls_subprocess(self, mock_config, existing_dirs, mock_subprocess):
        """監視フォルダを開く処理が正しく実行される"""
        app = TrayApp()
        app._open_folder(Path(r"C:\test\src"))
        mock_subprocess.Popen.assert_called_once_with(["explorer", r"C:\test\src"])


class TestTrayAppQuitApp:
    """アプリケーション終了のテスト"""

    def test_quit_app_stops_observer_and_icon(self, mock_config, existing_dirs, caplog):
        """終了時にobserverとiconを停止"""
        app = TrayApp()
        observer = MagicMock(spec=Observer)
        icon = MagicMock()
        app.observer = observer
        app.icon = icon

        with caplog.at_level(logging.INFO):
            app._quit_app()

        observer.stop.assert_called_once()
        observer.join.assert_called_once()
        icon.stop.assert_called_once()
        assert "アプリケーションを終了します" in caplog.text

    def test_quit_app_without_icon(self, mock_config, existing_dirs):
        """iconがNoneの場合でも正常終了"""
        app = TrayApp()
        observer = MagicMock(spec=Observer)
        app.observer = observer
        app.icon = None

        app._quit_app()
        observer.stop.assert_called_once()

    def test_quit_app_without_observer(self, mock_config, existing_dirs):
        """observerがNoneの場合でも正常終了"""
        app = TrayApp()
        icon = MagicMock()
        app.observer = None
        app.icon = icon

        app._quit_app()
        icon.stop.assert_called_once()


class TestTrayAppMenu:
    """メニュー作成のテスト"""

    def test_create_menu_structure(self, mock_config, existing_dirs, mock_pystray):
        """メニューが正しい構造で作成される"""
        app = TrayApp()
        app._create_menu()

        # pystray.Menuが呼ばれたことを確認
        assert mock_pystray.Menu.called

    def test_menu_lists_all_watch_folders(self, mock_config, existing_dirs, mock_pystray):
        """監視フォルダの数だけサブメニュー項目が作られる"""
        mock_config.return_value = [
            make_watch_rule(r"C:\test\src1"),
            make_watch_rule(r"C:\test\src2", targets=(r"C:\test\target2",)),
        ]
        app = TrayApp()
        app._create_menu()

        folder_texts = [
            call.kwargs["text"]
            for call in mock_pystray.MenuItem.call_args_list
            if "text" in call.kwargs
        ]
        assert "src1" in folder_texts
        assert "src2" in folder_texts
        assert "監視中: 2フォルダ" in folder_texts


class TestTrayAppWatching:
    """ファイル監視のテスト"""

    def test_start_watching_creates_observer(
        self, mock_config, existing_dirs, mock_observer, caplog
    ):
        """ファイル監視が正しく開始される"""
        with patch("app.tray_app.FileRenameHandler"):
            app = TrayApp()

            with caplog.at_level(logging.INFO):
                app.start_watching()

            mock_observer.assert_called_once()
            observer_instance = mock_observer.return_value
            observer_instance.schedule.assert_called_once()
            observer_instance.start.assert_called_once()
            assert "フォルダ監視を開始しました" in caplog.text

    def test_start_watching_schedules_each_watch_rule(
        self, mock_config, existing_dirs, mock_observer
    ):
        """監視フォルダごとにscheduleが呼ばれる"""
        mock_config.return_value = [
            make_watch_rule(r"C:\test\src1"),
            make_watch_rule(r"C:\test\src2", targets=(r"C:\test\target2",)),
        ]
        with patch("app.tray_app.FileRenameHandler"):
            app = TrayApp()
            app.start_watching()

        observer_instance = mock_observer.return_value
        assert observer_instance.schedule.call_count == 2
        scheduled_paths = [call.args[1] for call in observer_instance.schedule.call_args_list]
        assert scheduled_paths == [r"C:\test\src1", r"C:\test\src2"]

    def test_start_watching_passes_own_targets_to_handler(
        self, mock_config, existing_dirs, mock_observer
    ):
        """ハンドラには監視元ごとの移動先ルールが渡される"""
        mock_config.return_value = [
            make_watch_rule(r"C:\test\src1", targets=(r"C:\test\a",)),
            make_watch_rule(r"C:\test\src2", targets=(r"C:\test\b",)),
        ]
        with patch("app.tray_app.FileRenameHandler") as mock_handler:
            app = TrayApp()
            app.start_watching()

        passed_dirs = [str(call.args[0][0].directory) for call in mock_handler.call_args_list]
        assert passed_dirs == [r"C:\test\a", r"C:\test\b"]

    def test_stop_watching_stops_observer(self, mock_config, existing_dirs, caplog):
        """ファイル監視が正しく停止される"""
        app = TrayApp()
        observer = MagicMock(spec=Observer)
        app.observer = observer

        with caplog.at_level(logging.INFO):
            app.stop_watching()

        observer.stop.assert_called_once()
        observer.join.assert_called_once()
        assert "フォルダ監視を停止しました" in caplog.text

    def test_stop_watching_without_observer(self, mock_config, existing_dirs):
        """observerがNoneの場合でも正常終了"""
        app = TrayApp()
        app.observer = None
        # 例外が発生しないことを確認
        app.stop_watching()


class TestTrayAppRun:
    """アプリケーション実行のテスト"""

    def test_run_starts_thread_and_icon(self, mock_config, existing_dirs, mock_pystray):
        """runメソッドがスレッドとアイコンを起動"""
        with patch("app.tray_app.threading.Thread") as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance
            mock_icon_instance = MagicMock()
            mock_pystray.Icon.return_value = mock_icon_instance

            app = TrayApp()
            app.run()

            # スレッドが作成され、daemon=Trueで開始されることを確認
            mock_thread.assert_called_once()
            call_kwargs = mock_thread.call_args[1]
            assert call_kwargs["daemon"] is True
            mock_thread_instance.start.assert_called_once()

            # アイコンが作成され実行されることを確認
            mock_pystray.Icon.assert_called_once()
            mock_icon_instance.run.assert_called_once()

    def test_run_creates_icon_with_correct_params(self, mock_config, existing_dirs, mock_pystray):
        """アイコンが正しいパラメータで作成される"""
        with patch("app.tray_app.threading.Thread"):
            mock_icon_instance = MagicMock()
            mock_pystray.Icon.return_value = mock_icon_instance

            app = TrayApp()
            app.run()

            # Icon呼び出しの引数を確認
            call_kwargs = mock_pystray.Icon.call_args[1]
            assert call_kwargs["name"] == "FileTransfer"
            assert call_kwargs["title"] == "FileTransfer"
            assert "icon" in call_kwargs
            assert "menu" in call_kwargs
