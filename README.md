# FileTransfer

Windowsトレイアプリケーション。ディレクトリを監視して新しいファイルを自動的にリネーム・移動するツール。

## 主な機能

- Windows タスクトレイで常駐動作
- ファイル作成/移動イベントを自動検出
- ファイル名を設定パターンに基づいて自動リネーム
- 複数のターゲットディレクトリへの振り分け（ファイル名指定・ディレクトリごとのリネームパターン）
- Windows Explorer フォルダ表示の自動更新
- ログローテーション機能（日次で古いログ自動削除）

## 動作環境

- Windows 11
- Python 3.13以降

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
uv sync
```

### 4. 設定ファイルの編集

`utils/config.ini` を編集して監視フォルダとターゲットフォルダを指定。監視元ごとに `[WatchN]` セクションを作成：

```ini
[Watch1]
processing_dir = C:\path\to\monitoring\folder
target_dir1 = C:\path\to\target\folder1
filename1 = test1.md, test2.txt
regex1 = \.md$
pattern1 = _suffix
target_dir2 = C:\path\to\target\folder2
filename2 =
pattern2 =

[Watch2]
processing_dir = C:\another\folder
target_dir1 = C:\path\to\different\target
filename1 =
pattern1 =

[App]
wait_time = 0.5

[LOGGING]
log_retention_days = 7
log_directory = logs
log_level = INFO
debug_mode = False
project_name = FileTransfer
```

**監視元ごとの設定（`[WatchN]`）**
- `processing_dir`: 監視対象フォルダ
- `target_dirN`: ファイルの移動先フォルダ（`target_dir1`, `target_dir2`... と複数指定可）
- `filenameN`: `target_dirN` へ移動するファイル名（カンマ区切り、完全一致、拡張子込み）。空欄の場合は全ファイルが対象
- `regexN`: `target_dirN` へ移動するファイル名の正規表現（`filenameN` の完全一致に該当しない場合のみ判定）。空欄の場合は無効
- `patternN`: `target_dirN` へ移動する際にファイル名末尾（拡張子の前）に追加するサフィックス。空欄の場合は何も追加しない

**グローバル設定**
- `[App]` セクション: `wait_time` はファイル書き込み完了確認の待機時間（秒）
- `[LOGGING]` セクション: ログ設定（`log_retention_days`, `log_level`, `debug_mode`, `project_name` など）

**振り分けの優先順位**

1. `filenameN` で完全一致したルール（番号の若い順）
2. `regexN` で正規表現マッチしたルール（番号の若い順）
3. どちらにも該当しない場合は移動せず、ログに記録して監視フォルダに残す

## 使用方法

### アプリケーションの実行

```bash
python main.py
```

アプリケーションはタスクトレイで起動します。タスクトレイアイコンを右クリックすると、ログフォルダを開く、または終了することができます。

### ファイル処理フロー

アプリケーション起動時：
1. 設定ファイルから監視元（`processing_dir`）と移動先ルールを読み込む
2. 各監視元に既に存在するファイルを処理

ファイル作成/移動時：
1. `processing_dir` にファイルが作成/移動される
2. ファイルの書き込み完了を確認（ポーリング）
3. ファイル名から移動先（`target_dirN`）を決定（`filenameN` の完全一致、次に `regexN` の正規表現マッチを優先）
4. 移動先に対応する `patternN` に基づいてファイル名をリネーム
5. リネームされたファイルを移動先へ移動
6. Windows Explorer に変更を通知して フォルダ表示を更新

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
├── main.py                      # エントリーポイント
├── build.py                     # 実行ファイルビルドスクリプト
├── pyproject.toml               # プロジェクト設定・依存ライブラリ管理（uv）
├── uv.lock                      # ロックファイル（依存ライブラリバージョン固定）
├── CLAUDE.md                    # 開発ガイドライン
└── pyrightconfig.json           # 型チェッカー設定
```

## コアコンポーネント

### TrayApp（`app/tray_app.py`）

タスクトレイアイコンを作成・管理し、複数の監視元を監視するスレッドを実行。タスクトレイのメインスレッド上でアイコンを維持しながら、バックグラウンドで複数フォルダを監視します。

**主な機能**
- PIL/ImageDraw でタスクトレイアイコンを生成
- pystray でタスクトレイ操作を管理
- Watchdog Observer で複数フォルダのファイルシステムイベントを監視
- 監視元ごとに独立した FileRenameHandler を生成・管理
- 移動先が監視元と同一でないか起動時に検証

### FileRenameHandler（`service/file_rename_handler.py`）

Watchdog イベントハンドラー。ファイル作成/移動イベントを処理し、リネーム・移動を実行。設定をコンストラクタで受け取り、移動先ルールと待機時間に基づいてファイル処理を行います。

**主な機能**
- 監視開始前に既に存在するファイルの処理（`process_existing_files()` メソッド）
- ファイル書き込み完了確認（待機ループ）
- ファイル名から移動先ルールを解決（`filename` の完全一致を優先、次に `regex` の正規表現マッチ）
- 移動先ごとのリネームパターン（サフィックス）を適用
- Windows Shell API（`SHChangeNotify`）でExplorerの表示更新

```python
# ファイル処理例
from utils.config_manager import TargetRule
from service.file_rename_handler import FileRenameHandler
from pathlib import Path

targets = [
    TargetRule(directory=Path("C:/target1"), filename=["file1.txt"], regex=None, pattern="_suffix1"),
    TargetRule(directory=Path("C:/target2"), filename=[], regex=r"\.md$", pattern="_suffix2"),
]
handler = FileRenameHandler(targets=targets, wait_time=0.5)
handler.process_existing_files(Path("C:/monitoring"))  # 既存ファイルを処理
```

### ConfigManager（`utils/config_manager.py`）

`config.ini` の読み込み・保存、パス管理。複数の監視元（`[Watch1]`, `[Watch2]`...）をサポート。PyInstaller でビルドされた実行ファイルは `sys._MEIPASS` からの相対パスで設定ファイルを読み込みます。

**監視ルール（WatchRule）**
- 各 `[WatchN]` セクションは独立した監視元（`processing_dir`）と移動先ルールセット（`TargetRule` のリスト）を持つ

**振り分けルール（TargetRule）**
- `target_dirN` / `filenameN` / `regexN` / `patternN` を番号でペアリングし、番号の昇順で `TargetRule` のリストを構築
- `filenameN` は完全一致検査（カンマ区切りで複数指定可）
- `regexN` は正規表現マッチング（`filenameN` に該当しない場合のみ実行）、自動的に末尾を示す `$` が追加される
- `patternN` はファイル名末尾（拡張子の前）に追加するサフィックス
- `target_dirN` が1つも設定されていない場合は `ValueError` を送出

### LogRotation（`utils/log_rotation.py`）

`TimedRotatingFileHandler` を設定して日次ログローテーション。設定日数より古いログを自動削除します。

## 開発コマンド

### アプリケーション実行

```bash
python main.py
```

### テスト実行

```bash
python -m pytest tests/ -v --tb=short
```

テストは pytest 標準フレームワーク。カバレッジ追跡は pytest-cov で実施。

### 型チェック

```bash
pyright
```

`pyproject.toml` の `[tool.pyright]` セクションで Python 3.13、標準型チェックモードを設定。`app`, `service`, `utils`, `tests` ディレクトリをチェック。

### 実行ファイルビルド

```bash
python build.py
```

PyInstaller で実行ファイルをビルド（`--windowed` フラグ、`utils/config.ini` をバンドル）

## 設定ファイル詳細

### config.ini

```ini
[Watch1]
processing_dir = C:\path\to\monitoring
target_dir1 = C:\path\to\target
filename1 =
regex1 = \.md$
pattern1 = _suffix

[App]
wait_time = 0.5

[LOGGING]
log_retention_days = 7
log_directory = logs
log_level = INFO
debug_mode = False
project_name = FileTransfer
```

## Windows 固有の動作

- `ctypes.windll.shell32.SHChangeNotify` を使用して、ファイル操作後に Windows Explorer のフォルダ表示を自動更新
- タスクトレイアイコンは PIL/ImageDraw で動的に生成（青円+白いファイルアイコン）
- `subprocess.Popen(['explorer', path])` でエクスプローラーフォルダを開く

## ファイル処理の詳細

- イベント検出：`on_created` または `on_moved` イベント発火時に処理開始
- 上書き動作：ターゲット先に同名ファイルが存在する場合、確認なしで置き換え
- 正規表現処理：`regexN` で指定した正規表現の末尾には自動的に `$` が追加される（ファイル名末尾マッチング）
- 既存ファイル処理：監視開始時に各監視元フォルダに既に存在するファイルを処理

## トラブルシューティング

### フォルダが監視されない

1. `config.ini` の `processing_dir` が存在するか確認
2. パスに日本語を含む場合は UTF-8 エンコーディングで保存
3. ログ（`logs` ディレクトリ）でエラーメッセージを確認

### ファイルがリネームされない

1. `config.ini` の `filenameN` / `regexN` がファイルと一致しているか確認
2. `patternN` の番号が意図した `target_dirN` と一致しているか確認
3. `log_level = DEBUG` に変更してログを詳しく出力

### ファイルが移動されない

1. `filenameN` にファイル名が拡張子込みで正しく記載されているか確認
2. どの `filenameN` にも該当しないファイルを移動したい場合は、`filenameN` が空欄のターゲットを用意する
3. ログに「移動先が見つかりませんでした」が出力されていないか確認

### Windows Explorer にファイルが表示されない

1. ターゲットフォルダ（`target_dirN`）の存在確認
2. ターゲットフォルダの書き込み権限確認
3. エクスプローラーを手動で更新（F5キー）

### ポート/リソース競合エラー

1. 既存の FileTransfer プロセスが実行中でないか確認
2. タスクマネージャーで python.exe プロセスを確認
3. 必要に応じて強制終了

## ライセンス

このプロジェクトのライセンス情報については、 [LICENSE](docs/LICENSE) を参照してください。

## 更新履歴

更新履歴は [CHANGELOG.md](docs/CHANGELOG.md) を参照してください。
