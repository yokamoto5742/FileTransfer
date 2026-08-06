from __future__ import annotations

import logging
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

import pystray
from PIL import Image, ImageDraw
from watchdog.observers import Observer

from service.file_rename_handler import FileRenameHandler
from utils.config_manager import WatchRule, get_wait_time, get_watch_rules

logger = logging.getLogger(__name__)


class TrayApp:
    """タスクトレイアプリケーション"""

    def __init__(self) -> None:
        self.watch_rules: list[WatchRule] = get_watch_rules()
        self.observer: Optional[Observer] = None  # type: ignore[assignment]
        self.icon: Optional[pystray.Icon] = None  # type: ignore[assignment]
        self._validate_watch_rules()

    def _validate_watch_rules(self) -> None:
        """監視フォルダの存在確認と移動ループの検出"""
        existing = []
        for rule in self.watch_rules:
            if rule.source.exists():
                existing.append(rule)
            else:
                logger.error(f"監視フォルダが存在しません: {rule.source}")

        if not existing:
            logger.error("監視可能なフォルダがありません")
            sys.exit(1)

        self.watch_rules = existing
        self._reject_move_loops()

    def _reject_move_loops(self) -> None:
        """移動先が監視フォルダと同一の場合は無限ループになるため終了する"""
        sources = {rule.source.resolve() for rule in self.watch_rules}
        looped = [
            target.directory
            for rule in self.watch_rules
            for target in rule.targets
            if target.directory.resolve() in sources
        ]

        if looped:
            for directory in looped:
                logger.error(f"移動先が監視フォルダと同一です: {directory}")
            sys.exit(1)

    def _create_icon_image(self) -> Image.Image:
        """タスクトレイ用のアイコン画像を作成"""
        # 64x64の画像を作成
        size = 64
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # 背景円（青）
        draw.ellipse([4, 4, size - 4, size - 4], fill="#4A90D9")

        # ファイルアイコン風の図形（白）
        # 外枠
        draw.rectangle([20, 12, 44, 52], fill="white")
        # 折り返し部分
        draw.polygon([(32, 12), (44, 24), (32, 24)], fill="#4A90D9")

        # 矢印（リネームを表現）
        draw.line([(24, 38), (40, 38)], fill="#4A90D9", width=3)
        draw.polygon([(36, 33), (42, 38), (36, 43)], fill="#4A90D9")

        return image

    def _open_folder(self, folder: Path) -> None:
        """監視フォルダをエクスプローラーで開く"""
        subprocess.Popen(["explorer", str(folder)])

    def _quit_app(self) -> None:
        """アプリケーションを終了"""
        logger.info("アプリケーションを終了します")
        self.stop_watching()
        if self.icon:
            self.icon.stop()

    def _create_menu(self) -> pystray.Menu:
        """タスクトレイメニューを作成"""
        folder_items = [
            pystray.MenuItem(
                text=rule.source.name,
                # ループ内のlambdaはデフォルト引数でフォルダを束縛する
                action=lambda folder=rule.source: self._open_folder(folder),
            )
            for rule in self.watch_rules
        ]

        return pystray.Menu(
            pystray.MenuItem(
                text=f"監視中: {len(self.watch_rules)}フォルダ", action=None, enabled=False
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(text="監視フォルダを開く", action=pystray.Menu(*folder_items)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(text="終了", action=lambda: self._quit_app()),
        )

    def start_watching(self) -> None:
        """ファイル監視を開始"""
        wait_time = get_wait_time()
        observer = Observer()

        handlers = []
        for rule in self.watch_rules:
            event_handler = FileRenameHandler(list(rule.targets), wait_time)
            observer.schedule(event_handler, str(rule.source), recursive=False)
            logger.info(f"フォルダ監視を開始しました: {rule.source}")
            handlers.append((event_handler, rule.source))

        self.observer = observer
        observer.start()

        # 取りこぼしを防ぐため、監視開始後に既存ファイルを処理する
        for event_handler, source in handlers:
            event_handler.process_existing_files(source)

    def stop_watching(self) -> None:
        """ファイル監視を停止"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            logger.info("フォルダ監視を停止しました")

    def run(self) -> None:
        """アプリケーションを実行"""
        # ファイル監視を別スレッドで開始
        watch_thread = threading.Thread(target=self.start_watching, daemon=True)
        watch_thread.start()

        # タスクトレイアイコンを設定
        self.icon = pystray.Icon(
            name="FileTransfer",
            icon=self._create_icon_image(),
            title="FileTransfer",
            menu=self._create_menu(),
        )

        logger.info("タスクトレイに常駐しています")

        # タスクトレイアイコンを実行（メインスレッドでブロック）
        if self.icon is not None:
            self.icon.run()
