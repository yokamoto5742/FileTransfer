import logging
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler

from utils.config_manager import get_rename_patterns, get_wait_time

logger = logging.getLogger(__name__)


class FileRenameHandler(FileSystemEventHandler):
    """ファイルシステムイベントを処理し、ファイル名を変換するハンドラー"""

    def __init__(self):
        super().__init__()
        self.patterns = get_rename_patterns()
        self.wait_time = get_wait_time()

    def on_created(self, event):
        """新規ファイル作成時の処理"""
        if event.is_directory:
            return
        self._process_file(event.src_path)

    def on_moved(self, event):
        """ファイル移動時の処理（フォルダに移動されてきたファイル）"""
        if event.is_directory:
            return
        self._process_file(event.dest_path)

    def _process_file(self, file_path: str):
        """ファイルを処理してリネームする"""
        # ファイル書き込み完了を待つ
        time.sleep(self.wait_time)

        path = Path(file_path)
        if not path.exists():
            return

        filename = path.stem  # 拡張子を除いたファイル名
        extension = path.suffix  # 拡張子

        if self.should_rename(filename):
            self.rename_file(path, filename, extension)

    def should_rename(self, filename: str) -> bool:
        """ファイル名が変換対象かどうかを判定"""
        return any(pattern.search(filename) for pattern in self.patterns)

    def rename_file(self, file_path: Path, filename: str, extension: str):
        """ファイル名を変換する"""
        # 全パターンに一致する部分を削除
        new_filename = filename
        for pattern in self.patterns:
            new_filename = pattern.sub('', new_filename)
        new_file_path = file_path.parent / f"{new_filename}{extension}"

        # 変換後のファイル名が既に存在する場合は連番を付与
        base_name = new_filename
        counter = 1
        while new_file_path.exists():
            new_filename = f"{base_name} ({counter})"
            new_file_path = file_path.parent / f"{new_filename}{extension}"
            counter += 1

        try:
            file_path.rename(new_file_path)
            logger.info(f"リネーム完了: {file_path.name} -> {new_file_path.name}")
        except PermissionError:
            logger.error(f"ファイルにアクセスできません: {file_path}")
        except OSError as e:
            logger.error(f"リネーム失敗: {e}")
