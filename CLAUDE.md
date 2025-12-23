# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## House Rules:
- 文章ではなくパッチの差分を返す。
- コードの変更範囲は最小限に抑える。
- コードの修正は直接適用する。
- Pythonのコーディング規約はPEP8に従います。
- KISSの原則に従い、できるだけシンプルなコードにします。
- 可読性を優先します。一度読んだだけで理解できるコードが最高のコードです。
- Pythonのコードのimport文は以下の適切な順序に並べ替えてください。
標準ライブラリ
サードパーティライブラリ
カスタムモジュール 
それぞれアルファベット順に並べます。importが先でfromは後です。

## CHANGELOG
このプロジェクトにおけるすべての重要な変更は日本語でdcos/CHANGELOG.mdに記録します。
フォーマットは[Keep a Changelog](https://keepachangelog.com/ja/1.1.0/)に基づきます。

## Automatic Notifications (Hooks)
自動通知は`.claude/settings.local.json` で設定済：
- **Stop Hook**: ユーザーがClaude Codeを停止した時に「作業が完了しました」と通知
- **SessionEnd Hook**: セッション終了時に「Claude Code セッションが終了しました」と通知

## クリーンコードガイドライン
- 関数のサイズ：関数は50行以下に抑えることを目標にしてください。関数の処理が多すぎる場合は、より小さなヘルパー関数に分割してください。
- 単一責任：各関数とモジュールには明確な目的が1つあるようにします。無関係なロジックをまとめないでください。
- 命名：説明的な名前を使用してください。`tmp` 、`data`、`handleStuff`のような一般的な名前は避けてください。例えば、`doCalc`よりも`calculateInvoiceTotal` の方が適しています。
- DRY原則：コードを重複させないでください。類似のロジックが2箇所に存在する場合は、共有関数にリファクタリングしてください。それぞれに独自の実装が必要な場合はその理由を明確にしてください。
- コメント:分かりにくいロジックについては説明を加えます。説明不要のコードには過剰なコメントはつけないでください。
- コメントとdocstringは必要最小限に日本語で記述します。文末に"。"や"."をつけないでください。

## Project Overview

FileTransfer is a Windows tray application that monitors a directory for new files, automatically renames them based on configurable patterns, and moves them to a target directory. The application runs in the system tray with a custom icon and provides Windows Explorer integration with folder refresh notifications.

## Architecture

### Core Components

- **TrayApp** (`app/tray_app.py`): Main application that creates the system tray icon and manages the file watching lifecycle. Runs the file observer in a daemon thread while keeping the tray icon on the main thread.

- **FileRenameHandler** (`service/file_rename_handler.py`): Watchdog event handler that processes file creation/move events. Implements a wait-for-file-ready pattern to handle files that are still being written, then renames files based on regex patterns from config and moves them to the target directory. Uses Windows Shell API (`SHChangeNotify`) to refresh Explorer views.

- **ConfigManager** (`utils/config_manager.py`): Manages loading/saving `config.ini` settings. Handles PyInstaller frozen executable paths using `sys._MEIPASS`. Pattern matching uses regex with automatic `$` suffix for end-of-filename matching, sorted by pattern length (longest first).

- **LogRotation** (`utils/log_rotation.py`): Configures `TimedRotatingFileHandler` for daily log rotation with automatic cleanup of old logs. Supports separate debug logging when enabled.

### Configuration Flow

1. `config.ini` is loaded from the utils directory (or `sys._MEIPASS` in frozen builds)
2. Paths, rename patterns, and app settings are read on startup
3. File watcher monitors `processing_dir` and moves files to `target_dir`
4. Multiple patterns can be defined as `pattern1`, `pattern2`, etc. in the `[Rename]` section

### File Processing Flow

1. Watchdog detects file created/moved in `processing_dir`
2. `_wait_for_file_ready()` polls the file to ensure writing is complete
3. Check if filename already has a pattern suffix (skip rename if present)
4. If no pattern exists, append first pattern from config to filename
5. Move (or overwrite) file to `target_dir`
6. Call `SHChangeNotify` to refresh both source and target folders in Explorer

## Development Commands

### Running the Application

```bash
python main.py
```

### Running Tests

```bash
python -m pytest tests/ -v --tb=short --disable-warnings
```

### Type Checking

```bash
pyright
```

Configuration in `pyrightconfig.json`:
- Python 3.13
- Standard type checking mode
- Checks `app`, `service`, `utils` directories
- Excludes `tests`, `scripts`

### Building Executable

```bash
python build.py
```

This script:
- Increments the patch version in `app/__init__.py`
- Updates `docs/README.md` version and date (if present)
- Runs PyInstaller with `--windowed` flag
- Bundles `utils/config.ini` into the executable

## Important Implementation Details

### Windows-Specific Behavior

- Uses `ctypes.windll.shell32.SHChangeNotify` to refresh Explorer folder views after file operations
- Tray icon created with PIL/ImageDraw (blue circle with white file icon and arrow)
- Explorer integration via `subprocess.Popen(['explorer', path])`

### File Handling

- Files are processed when `on_created` or `on_moved` events fire
- Wait loop (default 0.5s × 10 retries) ensures file is not locked before processing
- Overwrite behavior: if destination file exists, it is replaced without prompting
- Regex patterns automatically get `$` appended if not present (for end-of-filename matching)

### Testing

- Tests use pytest framework
- Coverage tracking with pytest-cov
- Test structure mirrors source: tests for utils, service, app modules

### Versioning

- Version managed in `app/__init__.py` as `__version__` and `__date__`
- `scripts/version_manager.py` provides automatic version increment and sync to README
- Build process auto-increments patch version
