import logging
import os
import subprocess
import sys
import threading

import pystray
from PIL import Image, ImageDraw
from watchdog.observers import Observer

from service.file_rename_handler import FileRenameHandler
from utils.config_manager import get_src_dir

logger = logging.getLogger(__name__)


class TrayApp:
    """タスクトレイアプリケーション"""

    def __init__(self):
        self.src_dir = get_src_dir()
        self.observer = None
        self.icon = None
        self._validate_src_dir()

    def _validate_src_dir(self):
        """監視フォルダの存在確認"""
        if not os.path.exists(self.src_dir):
            logger.error(f"監視フォルダが存在しません: {self.src_dir}")
            sys.exit(1)

    def _create_icon_image(self) -> Image.Image:
        """タスクトレイ用のアイコン画像を作成"""
        # 64x64の画像を作成
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # 背景円（青）
        draw.ellipse([4, 4, size - 4, size - 4], fill='#4A90D9')

        # ファイルアイコン風の図形（白）
        # 外枠
        draw.rectangle([20, 12, 44, 52], fill='white')
        # 折り返し部分
        draw.polygon([(32, 12), (44, 24), (32, 24)], fill='#4A90D9')

        # 矢印（リネームを表現）
        draw.line([(24, 38), (40, 38)], fill='#4A90D9', width=3)
        draw.polygon([(36, 33), (42, 38), (36, 43)], fill='#4A90D9')

        return image

    def _open_folder(self):
        """監視フォルダをエクスプローラーで開く"""
        subprocess.Popen(['explorer', self.src_dir])

    def _quit_app(self):
        """アプリケーションを終了"""
        logger.info("アプリケーションを終了します")
        self.stop_watching()
        if self.icon:
            self.icon.stop()

    def _create_menu(self) -> pystray.Menu:
        """タスクトレイメニューを作成"""
        return pystray.Menu(
            pystray.MenuItem(
                text=f"監視中: {os.path.basename(self.src_dir)}",
                action=None,
                enabled=False
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                text="監視フォルダを開く",
                action=lambda: self._open_folder()
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                text="終了",
                action=lambda: self._quit_app()
            )
        )

    def start_watching(self):
        """ファイル監視を開始"""
        event_handler = FileRenameHandler()
        self.observer = Observer()
        self.observer.schedule(event_handler, self.src_dir, recursive=False)
        self.observer.start()
        logger.info(f"フォルダ監視を開始しました: {self.src_dir}")

    def stop_watching(self):
        """ファイル監視を停止"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            logger.info("フォルダ監視を停止しました")

    def run(self):
        """アプリケーションを実行"""
        # ファイル監視を別スレッドで開始
        watch_thread = threading.Thread(target=self.start_watching, daemon=True)
        watch_thread.start()

        # タスクトレイアイコンを設定
        self.icon = pystray.Icon(
            name="FileRenamer",
            icon=self._create_icon_image(),
            title="ファイル名自動変換",
            menu=self._create_menu()
        )

        logger.info("タスクトレイに常駐しています")

        # タスクトレイアイコンを実行（メインスレッドでブロック）
        self.icon.run()
