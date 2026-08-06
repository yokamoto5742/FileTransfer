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
target_dir1 = C:\path\to\target\folder1
filename1 = test1.md, test2.txt
target_dir2 = C:\path\to\target\folder2
filename2 =

[Rename]
pattern1 = _suffix
pattern2 =

[App]
wait_time = 0.5

[LOGGING]
log_retention_days = 7
log_directory = logs
log_level = INFO
debug_mode = False
```

- `processing_dir`: 監視対象フォルダ
- `target_dirN`: ファイルの移動先フォルダ（`target_dir1`, `target_dir2`... と複数指定可）
- `filenameN`: `target_dirN` へ移動するファイル名（カンマ区切り、拡張子込み）。空欄の場合は全ファイルが対象
- `patternN`: `target_dirN` へ移動する際にファイル名末尾（拡張子の前）に追加するパターン。空欄の場合は何も追加しない
- `wait_time`: ファイル書き込み完了確認の待機時間（秒）

**振り分けの優先順位**

1. `filenameN` にファイル名が指定されているルール（番号の若い順）
2. `filenameN` が空欄のルール（番号の若い順）
3. どちらにも該当しない場合は移動せず、ログに記録して監視フォルダに残す

## 使用方法

### アプリケーションの実行

```bash
python main.py
```

アプリケーションはタスクトレイで起動します。タスクトレイアイコンを右クリックすると、ログフォルダを開く、または終了することができます。

### ファイル処理フロー

1. `processing_dir` にファイルが作成/移動される
2. ファイルの書き込み完了を確認（約5秒間のポーリング）
3. ファイル名から移動先（`target_dirN`）を決定（`filenameN` の指定を優先）
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
- ファイル名から移動先ルールを解決（`filenameN` の指定を優先）
- 移動先ごとのリネームパターンを適用
- Windows Shell API（`SHChangeNotify`）でExplorerの表示更新

```python
# ファイル処理例
handler = FileRenameHandler()
# ファイルが processing_dir に作成されると自動処理
```

### ConfigManager（`utils/config_manager.py`）

`config.ini` の読み込み・保存、パス管理。PyInstaller でビルドされた実行ファイルは `sys._MEIPASS` からの相対パスで設定ファイルを読み込みます。

**振り分けルール（TargetRule）**
- `target_dirN` / `filenameN` / `patternN` を番号でペアリングし、番号の昇順で `TargetRule` のリストを構築
- 正規表現パターンに自動的に `$` サフィックスを追加（ファイル名末尾マッチング）
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
- `README.md` のバージョン・日付情報を更新
- PyInstaller で `--windowed` フラグ付きでビルド
- `utils/config.ini` を実行ファイルにバンドル

## 設定ファイル詳細

### config.ini

```ini
[Paths]
processing_dir = C:\Shinseikai\FileTransfer\processing
target_dir1 = C:\Users\yokam\Desktop\Magnate\file
filename1 =

[Rename]
pattern1 = _magnate

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
- パターン自動処理：正規表現パターンに自動的に `$` を追加（未指定時）

## トラブルシューティング

### フォルダが監視されない

1. `config.ini` の `processing_dir` が存在するか確認
2. パスに日本語を含む場合は UTF-8 エンコーディングで保存
3. ログ（`logs` ディレクトリ）でエラーメッセージを確認

### ファイルがリネームされない

1. `config.ini` の `patternN` が正規表現として正しいか確認
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

## バージョン情報

- **現在のバージョン**:1.0.0
- **最終更新日**: ：2025-12-23
- 更新履歴は [CHANGELOG.md](docs/CHANGELOG.md) を参照
