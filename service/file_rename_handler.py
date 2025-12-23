import ctypes
import logging
import shutil
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler

from utils.config_manager import get_rename_patterns, get_target_dir, get_wait_time

logger = logging.getLogger(__name__)

# Windows Shell通知用の定数
SHCNE_UPDATEDIR = 0x00001000
SHCNF_PATHW = 0x0005


def refresh_windows_folder(folder_path: str):
    """Windowsエクスプローラーのフォルダ表示を更新"""
    try:
        shell32 = ctypes.windll.shell32
        shell32.SHChangeNotify(SHCNE_UPDATEDIR, SHCNF_PATHW, folder_path, None)
    except Exception as e:
        logger.debug(f"フォルダ更新通知に失敗しました: {e}")


class FileRenameHandler(FileSystemEventHandler):
    """ファイルシステムイベントを処理し、ファイル名を変換するハンドラー"""

    def __init__(self):
        super().__init__()
        self.patterns = get_rename_patterns()
        self.wait_time = get_wait_time()
        self.target_dir = Path(get_target_dir())
        self._ensure_target_dir()

    def _ensure_target_dir(self):
        """移動先ディレクトリの存在を確認し、なければ作成"""
        if not self.target_dir.exists():
            self.target_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"移動先ディレクトリを作成しました: {self.target_dir}")

    def on_created(self, event):
        """新規ファイル作成時の処理"""
        if event.is_directory:
            return
        self._process_file(event.src_path)

    def on_moved(self, event):
        """ファイル移動時の処理"""
        if event.is_directory:
            return
        self._process_file(event.dest_path)

    def _wait_for_file_ready(self, path: Path, max_retries: int = 10) -> bool:
        """ファイルの書き込み完了を待つ"""
        for _ in range(max_retries):
            time.sleep(self.wait_time)
            if not path.exists():
                return False
            try:
                # ファイルが読み取り可能か確認
                with open(path, 'rb'):
                    pass
                return True
            except (IOError, PermissionError):
                continue
        return False

    def _process_file(self, file_path: str):
        """ファイルを処理してリネームし、移動する"""
        path = Path(file_path)

        # ファイル書き込み完了を待つ
        if not self._wait_for_file_ready(path):
            logger.warning(f"ファイルの準備ができませんでした: {path}")
            return

        if not path.exists():
            return

        filename = path.stem  # 拡張子を除いたファイル名
        extension = path.suffix  # 拡張子

        # パターンが既に付いているかチェック
        if self._has_pattern(filename):
            logger.debug(f"パターンは既に付いています: {filename}")
            # パターンが既にある場合はそのまま移動
            self._move_file(path)
            return

        # パターンを追加してリネーム＆移動
        self._rename_and_move_file(path, filename, extension)

    def _has_pattern(self, filename: str) -> bool:
        """ファイル名に既にパターンが付いているかチェック"""
        for pattern in self.patterns:
            if pattern.search(filename):
                return True
        return False

    def _rename_and_move_file(self, path: Path, filename: str, extension: str):
        """ファイル名にパターンを追加し、target_dirに移動する"""
        # 最初のパターンを使用（config.iniのpatternの値を取得）
        # パターンから末尾の$を除去して実際の追加文字列を取得
        if not self.patterns:
            logger.warning("リネームパターンが設定されていません")
            self._move_file(path)
            return

        pattern_str = self.patterns[0].pattern
        # $を除去してサフィックスを取得
        suffix = pattern_str.rstrip('$')

        new_filename = f"{filename}{suffix}{extension}"
        new_path = self.target_dir / new_filename

        try:
            # 同名ファイルが存在する場合は上書き
            if new_path.exists():
                logger.info(f"既存ファイルを上書きします: {new_path}")
            source_dir = str(path.parent)
            shutil.move(str(path), str(new_path))
            logger.info(f"ファイルをリネーム＆移動しました: {path.name} -> {new_path}")
            # エクスプローラーの表示を更新
            refresh_windows_folder(source_dir)
            refresh_windows_folder(str(self.target_dir))
        except Exception as e:
            logger.error(f"ファイルの移動に失敗しました: {path} -> {new_path}, エラー: {e}")

    def _move_file(self, path: Path):
        """ファイルをtarget_dirに移動する（リネームなし）"""
        new_path = self.target_dir / path.name

        try:
            # 同名ファイルが存在する場合は上書き
            if new_path.exists():
                logger.info(f"既存ファイルを上書きします: {new_path}")
            source_dir = str(path.parent)
            shutil.move(str(path), str(new_path))
            logger.info(f"ファイルを移動しました: {path.name} -> {new_path}")
            # エクスプローラーの表示を更新
            refresh_windows_folder(source_dir)
            refresh_windows_folder(str(self.target_dir))
        except Exception as e:
            logger.error(f"ファイルの移動に失敗しました: {path} -> {new_path}, エラー: {e}")
