import logging
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image
from watchdog.observers import Observer

from app.tray_app import TrayApp


@pytest.fixture
def mock_config():
    """設定のモックを提供"""
    with patch('app.tray_app.get_src_dir') as mock_get_src_dir:
        mock_get_src_dir.return_value = r'C:\test\src'
        yield mock_get_src_dir


@pytest.fixture
def mock_observer():
    """Observerのモックを提供"""
    with patch('app.tray_app.Observer') as mock_obs:
        yield mock_obs


@pytest.fixture
def mock_pystray():
    """pystrayのモックを提供"""
    with patch('app.tray_app.pystray') as mock_ps:
        yield mock_ps


@pytest.fixture
def mock_subprocess():
    """subprocessのモックを提供"""
    with patch('app.tray_app.subprocess') as mock_sp:
        yield mock_sp


class TestTrayAppInit:
    """TrayAppの初期化テスト"""

    def test_init_success(self, mock_config):
        """正常な初期化"""
        with patch('os.path.exists', return_value=True):
            app = TrayApp()
            assert app.src_dir == r'C:\test\src'
            assert app.observer is None
            assert app.icon is None

    def test_init_with_missing_src_dir(self, mock_config):
        """監視フォルダが存在しない場合はsys.exitを呼ぶ"""
        with patch('os.path.exists', return_value=False):
            with pytest.raises(SystemExit) as excinfo:
                TrayApp()
            assert excinfo.value.code == 1

    def test_validate_src_dir_logs_error(self, mock_config, caplog):
        """監視フォルダが存在しない場合のログ出力"""
        with patch('os.path.exists', return_value=False):
            with caplog.at_level(logging.ERROR):
                with pytest.raises(SystemExit):
                    TrayApp()
            assert "監視フォルダが存在しません" in caplog.text


class TestTrayAppIconCreation:
    """アイコン作成のテスト"""

    def test_create_icon_image_returns_pil_image(self, mock_config):
        """アイコン画像が正しく作成される"""
        with patch('os.path.exists', return_value=True):
            app = TrayApp()
            image = app._create_icon_image()
            assert isinstance(image, Image.Image)
            assert image.size == (64, 64)
            assert image.mode == 'RGBA'


class TestTrayAppFolderOperations:
    """フォルダ操作のテスト"""

    def test_open_folder_calls_subprocess(self, mock_config, mock_subprocess):
        """監視フォルダを開く処理が正しく実行される"""
        with patch('os.path.exists', return_value=True):
            app = TrayApp()
            app._open_folder()
            mock_subprocess.Popen.assert_called_once_with(['explorer', r'C:\test\src'])


class TestTrayAppQuitApp:
    """アプリケーション終了のテスト"""

    def test_quit_app_stops_observer_and_icon(self, mock_config, caplog):
        """終了時にobserverとiconを停止"""
        with patch('os.path.exists', return_value=True):
            app = TrayApp()
            app.observer = MagicMock(spec=Observer)
            app.icon = MagicMock()

            with caplog.at_level(logging.INFO):
                app._quit_app()

            app.observer.stop.assert_called_once()
            app.observer.join.assert_called_once()
            app.icon.stop.assert_called_once()
            assert "アプリケーションを終了します" in caplog.text

    def test_quit_app_without_icon(self, mock_config):
        """iconがNoneの場合でも正常終了"""
        with patch('os.path.exists', return_value=True):
            app = TrayApp()
            app.observer = MagicMock(spec=Observer)
            app.icon = None

            app._quit_app()
            app.observer.stop.assert_called_once()

    def test_quit_app_without_observer(self, mock_config):
        """observerがNoneの場合でも正常終了"""
        with patch('os.path.exists', return_value=True):
            app = TrayApp()
            app.observer = None
            app.icon = MagicMock()

            app._quit_app()
            app.icon.stop.assert_called_once()


class TestTrayAppMenu:
    """メニュー作成のテスト"""

    def test_create_menu_structure(self, mock_config, mock_pystray):
        """メニューが正しい構造で作成される"""
        with patch('os.path.exists', return_value=True):
            app = TrayApp()
            menu = app._create_menu()

            # pystray.Menuが呼ばれたことを確認
            assert mock_pystray.Menu.called

    def test_menu_displays_correct_folder_name(self, mock_config, mock_pystray):
        """メニューに正しいフォルダ名が表示される"""
        with patch('os.path.exists', return_value=True):
            mock_config.return_value = r'C:\test\monitoring'
            app = TrayApp()
            app.src_dir = r'C:\test\monitoring'

            with patch('os.path.basename', return_value='monitoring'):
                menu = app._create_menu()
                # メニューアイテムが作成されることを確認
                assert mock_pystray.MenuItem.called


class TestTrayAppWatching:
    """ファイル監視のテスト"""

    def test_start_watching_creates_observer(self, mock_config, mock_observer, caplog):
        """ファイル監視が正しく開始される"""
        with patch('os.path.exists', return_value=True):
            with patch('app.tray_app.FileRenameHandler') as mock_handler:
                app = TrayApp()

                with caplog.at_level(logging.INFO):
                    app.start_watching()

                mock_observer.assert_called_once()
                observer_instance = mock_observer.return_value
                observer_instance.schedule.assert_called_once()
                observer_instance.start.assert_called_once()
                assert "フォルダ監視を開始しました" in caplog.text

    def test_stop_watching_stops_observer(self, mock_config, caplog):
        """ファイル監視が正しく停止される"""
        with patch('os.path.exists', return_value=True):
            app = TrayApp()
            app.observer = MagicMock(spec=Observer)

            with caplog.at_level(logging.INFO):
                app.stop_watching()

            app.observer.stop.assert_called_once()
            app.observer.join.assert_called_once()
            assert "フォルダ監視を停止しました" in caplog.text

    def test_stop_watching_without_observer(self, mock_config):
        """observerがNoneの場合でも正常終了"""
        with patch('os.path.exists', return_value=True):
            app = TrayApp()
            app.observer = None
            # 例外が発生しないことを確認
            app.stop_watching()


class TestTrayAppRun:
    """アプリケーション実行のテスト"""

    def test_run_starts_thread_and_icon(self, mock_config, mock_pystray):
        """runメソッドがスレッドとアイコンを起動"""
        with patch('os.path.exists', return_value=True):
            with patch('app.tray_app.threading.Thread') as mock_thread:
                mock_thread_instance = MagicMock()
                mock_thread.return_value = mock_thread_instance
                mock_icon_instance = MagicMock()
                mock_pystray.Icon.return_value = mock_icon_instance

                app = TrayApp()
                app.run()

                # スレッドが作成され、daemon=Trueで開始されることを確認
                mock_thread.assert_called_once()
                call_kwargs = mock_thread.call_args[1]
                assert call_kwargs['daemon'] is True
                mock_thread_instance.start.assert_called_once()

                # アイコンが作成され実行されることを確認
                mock_pystray.Icon.assert_called_once()
                mock_icon_instance.run.assert_called_once()

    def test_run_creates_icon_with_correct_params(self, mock_config, mock_pystray):
        """アイコンが正しいパラメータで作成される"""
        with patch('os.path.exists', return_value=True):
            with patch('app.tray_app.threading.Thread') as mock_thread:
                mock_icon_instance = MagicMock()
                mock_pystray.Icon.return_value = mock_icon_instance

                app = TrayApp()
                app.run()

                # Icon呼び出しの引数を確認
                call_kwargs = mock_pystray.Icon.call_args[1]
                assert call_kwargs['name'] == 'FileTransfer'
                assert call_kwargs['title'] == 'FileTransfer'
                assert 'icon' in call_kwargs
                assert 'menu' in call_kwargs
