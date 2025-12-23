# FileTransfer

Windowsトレイアプリケーション。ディレクトリを監視して新しいファイルを自動的にリネーム・移動するツール。

## 主な機能

- Windows タスクトレイで常駐動作
- ファイル作成/移動イベントを自動検出
- ファイル名を設定パターンに基づいて自動リネーム
- ターゲットディレクトリへの自動移動
- Windows Explorer フォルダ表示の自動更新
- ログローテーション機能（日次で古いログ自動削除）

## 動作環境

- Windows 10/11
- Python 3.13+

## インストール

### 1. リポジトリのクローン

```bash
git clone https://github.com/yokam/FileTransfer.git
cd FileTransfer
```

### 2. 仮想環境の構築

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. 依存ライブラリのインストール

```bash
pip install -r requirements.txt
```

### 4. 設定ファイルの編集

`utils/config.ini` を編集して監視フォルダとターゲットフォルダを指定：

```ini
[Paths]
processing_dir = C:\path\to\monitoring\folder
target_dir = C:\path\to\target\folder

[Rename]
pattern = _suffix

[App]
wait_time = 0.5

[LOGGING]
log_retention_days = 7
log_directory = logs
log_level = INFO
debug_mode = False
```

- `processing_dir`: 監視対象フォルダ
- `target_dir`: ファイルの移動先フォルダ
- `pattern`: ファイル名に追加するパターン（複数パターンは `pattern1`, `pattern2` など）
- `wait_time`: ファイル書き込み完了確認の待機時間（秒）

## 使用方法

### アプリケーションの実行

```bash
python main.py
```

アプリケーションはタスクトレイで起動します。タスクトレイアイコンを右クリックすると、ログフォルダを開く、または終了することができます。

### ファイル処理フロー

1. `processing_dir` にファイルが作成/移動される
2. ファイルの書き込み完了を確認（約5秒間のポーリング）
3. ファイル名がパターンに基づいてリネーム
4. リネームされたファイルを `target_dir` に移動
5. Windows Explorer に変更を通知して フォルダ表示を更新

## プロジェクト構成

```
FileTransfer/
├── app/
│   ├── __init__.py              # バージョン・日付情報
│   └── tray_app.py              # タスクトレイアプリケーション
├── service/
│   └── file_rename_handler.py   # ファイル処理ハンドラー
├── utils/
│   ├── config_manager.py        # 設定ファイル管理
│   ├── config.ini               # 設定ファイル
│   └── log_rotation.py          # ログローテーション設定
├── tests/                       # ユニットテスト
├── scripts/
│   └── version_manager.py       # バージョン管理ユーティリティ
├── main.py                      # エントリーポイント
├── build.py                     # 実行ファイルビルドスクリプト
├── CLAUDE.md                    # 開発ガイドライン
└── requirements.txt             # 依存ライブラリ
```

## コアコンポーネント

### TrayApp（`app/tray_app.py`）

タスクトレイアイコンを作成・管理し、ファイル監視スレッドを実行。タスクトレイのメインスレッド上でアイコンを維持しながら、バックグラウンドでファイル監視を行います。

**主な機能**
- PIL/ImageDraw でタスクトレイアイコンを生成
- pystray でタスクトレイ操作を管理
- Watchdog Observer でファイルシステムイベントを監視

### FileRenameHandler（`service/file_rename_handler.py`）

Watchdog イベントハンドラー。ファイル作成/移動イベントを処理し、リネーム・移動を実行。

**主な機能**
- ファイル書き込み完了確認（待機ループ）
- 設定からリネームパターンを取得して適用
- Windows Shell API（`SHChangeNotify`）でExplorerの表示更新
- ターゲットディレクトリへの移動

```python
# ファイル処理例
handler = FileRenameHandler()
# ファイルが processing_dir に作成されると自動処理
```

### ConfigManager（`utils/config_manager.py`）

`config.ini` の読み込み・保存、パス管理。PyInstaller でビルドされた実行ファイルは `sys._MEIPASS` からの相対パスで設定ファイルを読み込みます。

**パターンマッチング**
- 正規表現パターンに自動的に `$` サフィックスを追加（ファイル名末尾マッチング）
- 複数パターンはパターン長でソート（長いものを優先）

### LogRotation（`utils/log_rotation.py`）

`TimedRotatingFileHandler` を設定して日次ログローテーション。設定日数より古いログを自動削除します。

## 開発コマンド

### アプリケーション実行

```bash
python main.py
```

### テスト実行

```bash
python -m pytest tests/ -v --tb=short --disable-warnings
```

テストは pytest 標準フレームワーク。カバレッジ追跡は pytest-cov で実施。

### 型チェック

```bash
pyright
```

`pyrightconfig.json` で Python 3.13、標準型チェックモードを設定。`app`, `service`, `utils` ディレクトリをチェック。

### 実行ファイルビルド

```bash
python build.py
```

自動実行内容：
- `app/__init__.py` 内のパッチバージョンをインクリメント
- `docs/README.md` のバージョン・日付情報を更新
- PyInstaller で `--windowed` フラグ付きでビルド
- `utils/config.ini` を実行ファイルにバンドル

## 設定ファイル詳細

### config.ini

```ini
[Paths]
processing_dir = C:\Shinseikai\FileTransfer\processing
target_dir = C:\Users\yokam\Desktop\Magnate\file

[Rename]
pattern = _magnate

[App]
wait_time = 0.5

[LOGGING]
log_retention_days = 7
log_directory = logs
log_level = INFO
debug_mode = False
project_name = FileTransfer
```

**パラメータ説明**

| セクション | キー | 説明 | デフォルト |
|-----------|------|------|----------|
| Paths | processing_dir | 監視フォルダのパス | 必須 |
| Paths | target_dir | 移動先フォルダのパス | 必須 |
| Rename | pattern | ファイル名に追加するパターン（複数可） | 必須 |
| App | wait_time | ファイル書き込み完了待機時間（秒） | 0.5 |
| LOGGING | log_retention_days | ログ保持日数 | 7 |
| LOGGING | log_directory | ログ出力ディレクトリ | logs |
| LOGGING | log_level | ログレベル (DEBUG/INFO/WARNING/ERROR) | INFO |
| LOGGING | debug_mode | 詳細ログ出力有効化 | False |
| LOGGING | project_name | ログ出力用プロジェクト名 | FileTransfer |

## Windows 固有の動作

- `ctypes.windll.shell32.SHChangeNotify` を使用して、ファイル操作後に Windows Explorer のフォルダ表示を自動更新
- タスクトレイアイコンは PIL/ImageDraw で動的に生成（青円+白いファイルアイコン）
- `subprocess.Popen(['explorer', path])` でエクスプローラーフォルダを開く

## ファイル処理の詳細

- イベント検出：`on_created` または `on_moved` イベント発火時に処理開始
- ファイル準備確認：約5秒間のポーリング（デフォルト0.5秒×10回）でファイルロック解除を確認
- 上書き動作：ターゲット先に同名ファイルが存在する場合、確認なしで置き換え
- パターン自動処理：正規表現パターンに自動的に `$` を追加（未指定時）

## トラブルシューティング

### フォルダが監視されない

1. `config.ini` の `processing_dir` が存在するか確認
2. パスに日本語を含む場合は UTF-8 エンコーディングで保存
3. ログ（`logs/` ディレクトリ）でエラーメッセージを確認

### ファイルがリネームされない

1. `config.ini` の `pattern` が正規表現として正しいか確認
2. パターンが複数ある場合、優先順位（パターン長で降順）を確認
3. `log_level = DEBUG` に変更してログを詳しく出力

### Windows Explorer にファイルが表示されない

1. ターゲットフォルダ（`target_dir`）の存在確認
2. ターゲットフォルダの書き込み権限確認
3. エクスプローラーを手動で更新（F5キー）

### ポート/リソース競合エラー

1. 既存の FileTransfer プロセスが実行中でないか確認
2. タスクマネージャーで python.exe プロセスを確認
3. 必要に応じて強制終了

## ライセンス

詳細は [LICENSE](./LICENSE) を参照してください。

## バージョン情報

- 現在バージョン：1.0.0
- 更新日：2025-12-23
- 更新履歴は [CHANGELOG.md](./CHANGELOG.md) を参照
