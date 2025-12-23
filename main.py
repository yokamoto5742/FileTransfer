import logging
import sys

from app.tray_app import TrayApp
from utils.log_rotation import setup_logging

logger = logging.getLogger(__name__)


def main():
    setup_logging()

    try:
        app = TrayApp()
        app.run()
    except FileNotFoundError as e:
        logger.error(f"設定ファイルエラー: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"予期せぬエラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
