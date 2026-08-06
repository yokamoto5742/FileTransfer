from __future__ import annotations

import ctypes
import logging
import shutil
import time
from pathlib import Path
from typing import Optional

from watchdog.events import FileSystemEventHandler, FileSystemEvent

from utils.config_manager import TargetRule

logger = logging.getLogger(__name__)

# Windows Shell通知用の定数
SHCNE_UPDATEDIR = 0x00001000
SHCNF_PATHW = 0x0005


def refresh_windows_folder(folder_path: str) -> None:
    """Windowsエクスプローラーのフォルダ表示を更新"""
    try:
        shell32 = ctypes.windll.shell32
        shell32.SHChangeNotify(SHCNE_UPDATEDIR, SHCNF_PATHW, folder_path, None)
    except Exception as e:
        logger.debug(f"フォルダ更新通知に失敗しました: {e}")


class FileRenameHandler(FileSystemEventHandler):
    """ファイルシステムイベントを処理し、ファイル名を変換するハンドラー"""

    def __init__(self, targets: list[TargetRule], wait_time: float) -> None:
        super().__init__()
        self.targets: list[TargetRule] = targets
        self.wait_time: float = wait_time
        self._ensure_target_dirs()

    def _ensure_target_dirs(self) -> None:
        """全ての移動先ディレクトリの存在を確認し、なければ作成"""
        for rule in self.targets:
            if not rule.directory.exists():
                rule.directory.mkdir(parents=True, exist_ok=True)
                logger.info(f"移動先ディレクトリを作成しました: {rule.directory}")

    def process_existing_files(self, directory: Path) -> None:
        """監視開始前から存在するファイルを処理する"""
        for path in sorted(directory.iterdir()):
            if path.is_file():
                self._process_file(str(path))

    def on_created(self, event: FileSystemEvent) -> None:
        """新規ファイル作成時の処理"""
        if event.is_directory:
            return

        src_path = event.src_path if isinstance(event.src_path, str) else event.src_path.decode()
        self._process_file(src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        """ファイル移動時の処理"""
        if event.is_directory:
            return

        dest_path = (
            event.dest_path if isinstance(event.dest_path, str) else event.dest_path.decode()
        )
        self._process_file(dest_path)

    def _wait_for_file_ready(self, path: Path, max_retries: int = 10) -> bool:
        """ファイルの書き込み完了を待つ"""
        for _ in range(max_retries):
            time.sleep(self.wait_time)
            if not path.exists():
                return False
            try:
                # ファイルが読み取り可能か確認
                with open(path, "rb"):
                    pass
                return True
            except (IOError, PermissionError):
                continue
        return False

    def _process_file(self, file_path: str) -> None:
        """ファイルを処理してリネームし移動する"""
        path = Path(file_path)

        # ファイル書き込み完了を待つ
        if not self._wait_for_file_ready(path):
            logger.warning(f"ファイルの準備ができませんでした: {path}")
            return

        if not path.exists():
            return

        rule = self._resolve_rule(path.name)
        if rule is None:
            logger.info(f"移動先が見つかりませんでした: {path.name}")
            return

        self._move_file(path, rule)

    def _resolve_rule(self, filename: str) -> Optional[TargetRule]:
        """ファイル名に対応する移動先ルールを取得（完全一致 > 正規表現 > 全件受け入れの順）"""
        name = filename.lower()

        for rule in self.targets:
            if name in rule.filenames:
                return rule

        for rule in self.targets:
            if rule.filename_regex is not None and rule.filename_regex.search(filename):
                return rule

        # ファイル名指定も正規表現指定もないルールは全ファイルを受け入れる
        for rule in self.targets:
            if not rule.filenames and rule.filename_regex is None:
                return rule

        return None

    def _build_target_name(self, path: Path, rule: TargetRule) -> str:
        """移動先でのファイル名を組み立てる（必要ならサフィックスを付加）"""
        if rule.pattern is None or rule.pattern.search(path.stem):
            return path.name

        return f"{path.stem}{rule.suffix}{path.suffix}"

    def _move_file(self, path: Path, rule: TargetRule) -> None:
        """ファイルを移動先ディレクトリへ（必要ならリネームして）移動する"""
        new_path = rule.directory / self._build_target_name(path, rule)

        try:
            if new_path.exists():
                logger.info(f"既存ファイルを上書きします: {new_path}")
            source_dir = str(path.parent)
            shutil.move(str(path), str(new_path))
            logger.info(f"ファイルを移動しました: {path.name} -> {new_path}")
            # エクスプローラーの表示を更新
            refresh_windows_folder(source_dir)
            refresh_windows_folder(str(rule.directory))
        except Exception as e:
            logger.error(f"ファイルの移動に失敗しました: {path} -> {new_path}, エラー: {e}")
