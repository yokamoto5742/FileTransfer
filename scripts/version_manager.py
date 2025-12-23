import os
import re
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_INIT_PATH = os.path.join(PROJECT_ROOT, "app", "__init__.py")
README_PATH = os.path.join(PROJECT_ROOT, "docs", "README.md")


def get_current_version():
    try:
        with open(APP_INIT_PATH, encoding='utf-8') as f:
            content = f.read()

        match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            return match.group(1)
        else:
            print("Warning: __version__ が見つかりません。")
            return "0.0.0"
    except FileNotFoundError:
        print(f"Error: {APP_INIT_PATH} が見つかりません。")
        return "0.0.0"
    except Exception as e:
        print(f"Error: バージョン取得中にエラーが発生しました: {e}")
        return "0.0.0"


def get_current_date():
    try:
        with open(APP_INIT_PATH, encoding='utf-8') as f:
            content = f.read()

        match = re.search(r'__date__\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            return match.group(1)
        else:
            print("Warning: __date__ が見つかりません。現在の日付を返します。")
            return datetime.now().strftime("%Y-%m-%d")
    except FileNotFoundError:
        print(f"Error: {APP_INIT_PATH} が見つかりません。")
        return datetime.now().strftime("%Y-%m-%d")
    except Exception as e:
        print(f"Error: 日付取得中にエラーが発生しました: {e}")
        return datetime.now().strftime("%Y-%m-%d")


def increment_version(version, increment_type="patch"):
    try:
        major, minor, patch = map(int, version.split("."))
        return f"{major}.{minor}.{patch + 1}"
    except ValueError as e:
        print(f"Error: 無効なバージョン形式: {version}")
        return "0.0.0"


def update_app_init(new_version, new_date):
    try:
        with open(APP_INIT_PATH, encoding='utf-8') as f:
            content = f.read()

        new_content = re.sub(
            r'(__version__\s*=\s*["\'])[^"\']+(["\'])',
            rf'\g<1>{new_version}\g<2>',
            content
        )

        new_content = re.sub(
            r'(__date__\s*=\s*["\'])[^"\']+(["\'])',
            rf'\g<1>{new_date}\g<2>',
            new_content
        )

        with open(APP_INIT_PATH, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"app/__init__.py を更新しました: v{new_version} ({new_date})")
        return True

    except Exception as e:
        print(f"Error: app/__init__.py の更新中にエラーが発生しました: {e}")
        return False


def update_readme(new_version, new_date):
    try:
        with open(README_PATH, encoding='utf-8') as f:
            content = f.read()

        new_content = re.sub(
            r'(\*\*現在のバージョン\*\*:\s*)[^\n]+',
            rf'\g<1>{new_version}',
            content
        )

        date_obj = datetime.strptime(new_date, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%Y年%m月%d日").replace("月0", "月").replace("日0", "日")

        new_content = re.sub(
            r'(\*\*最終更新日\*\*:\s*)[^\n]+',
            rf'\g<1>{formatted_date}',
            new_content
        )

        with open(README_PATH, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"README.md を更新しました")
        return True

    except FileNotFoundError:
        print(f"Warning: {README_PATH} が見つかりません。READMEの更新をスキップします。")
        return False
    except Exception as e:
        print(f"Error: README.md の更新中にエラーが発生しました: {e}")
        return False


def update_version(increment_type="patch"):
    current_version = get_current_version()
    new_version = increment_version(current_version, increment_type)
    new_date = datetime.now().strftime("%Y-%m-%d")

    app_success = update_app_init(new_version, new_date)
    readme_success = update_readme(new_version, new_date)

    if app_success:
        print(f"バージョン更新完了: {current_version} -> {new_version}")
        return new_version
    else:
        print("バージョン更新に失敗しました")
        return current_version
