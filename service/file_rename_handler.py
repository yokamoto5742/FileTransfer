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
        """ファイル移動時の処理"""
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
