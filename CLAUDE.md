# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

FileTransferは、指定フォルダを監視し、新規作成/移動されたファイルを設定済みの正規表現パターンでリネームして対象ディレクトリへ移動するWindows常駐トレイアプリケーション。移動後にWindows ExplorerのビューをSHChangeNotifyで更新する。

## アーキテクチャ

- `main.py` — エントリーポイント。ロギングを初期化し `TrayApp` を起動。
- `app/tray_app.py` — `TrayApp`: pystrayによるトレイアイコンを管理し、バックグラウンドスレッドで`watchdog.Observer`により`processing_dir`を監視。
- `service/file_rename_handler.py` — `FileRenameHandler`: ファイル作成/移動イベントを検知し、書き込み完了を待ってから正規表現パターン（最長一致優先、末尾に`$`を自動付与）でリネームし`target_dir`へ移動。`SHChangeNotify`（ctypes経由）でExplorerを更新。
- `utils/config_manager.py` — `utils/config.ini`の読み込み/保存。PyInstallerでフリーズされた実行ファイルでは`sys._MEIPASS`からパスを解決。
- `utils/log_rotation.py` — `TimedRotatingFileHandler`による日次ログローテーションと古いログの自動削除を設定。

## 依存関係管理

本プロジェクトは **uv** で依存関係を管理する（`pyproject.toml` + `uv.lock`）。`requirements.txt`は存在しない。依存関係の追加・更新は`uv add` / `uv sync`を使用する。

## 型チェック

pyright設定は`pyrightconfig.json`ではなく`pyproject.toml`の`[tool.pyright]`にある。`app`, `service`, `utils`, `tests`を対象とし、`scripts`を除外。

```bash
pyright
```

## ビルド

```bash
python build.py
```

`app/__init__.py`のパッチバージョンを自動インクリメントし、`docs/README.md`のバージョン/更新日を書き換えたうえで、PyInstallerを実行する（`--windowed`、`utils/config.ini`を同梱）。

## 実行時設定

`utils/config.ini`に実際の稼働設定が直接コミットされている（テンプレートではない）。
- `[Paths]`: `processing_dir`, `target_dir`
- `[Rename]`: `pattern`, `pattern1`, `pattern2`...（正規表現）
- `[App]`: `wait_time`
- `[LOGGING]`: `log_retention_days`, `log_directory`, `log_level`, `debug_mode`, `project_name`

## コーディング規約・コミット規約・テスト

コーディングスタイル、コミットメッセージ形式、レスポンス形式、テスト実行コマンドは `.claude/rules/` 配下に分割されている（`coding-guidelines.md`, `commit.md`, `python-coding.md`, `response-style.md`, `testing.md`）。これらは自動的に読み込まれるため、ここでは重複させない。

## 変更履歴

`docs/CHANGELOG.md`に[Keep a Changelog](https://keepachangelog.com/ja/1.1.0/)形式で記録する。
