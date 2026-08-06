# 変更ログ

このプロジェクトのすべての重要な変更はこのファイルに記録されます。

このファイルのフォーマットは [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) に基づいており、
バージョニングは [Semantic Versioning](https://semver.org/lang/ja/) に従っています。

## [Unreleased]

### 追加
- 移動先ディレクトリを `target_dir1`, `target_dir2`... と複数指定できる機能
- 移動先ごとに移動対象のファイル名を指定する `filename1`, `filename2`... を追加（カンマ区切りで複数指定可、空欄の場合は全ファイルが対象）
- 移動先ごとにリネームパターンを切り替える機能（`[Rename]` の `pattern1`, `pattern2`... が `target_dirN` に対応）
- config_manager の単体テスト

### 変更
- **破壊的変更**: `[Paths]` の `target_dir` を廃止し、番号付きの `target_dir1` 以降に統一
- **破壊的変更**: `[Rename]` の `patternN` の意味を「複数のリネームパターン」から「`target_dirN` ごとのリネームパターン」に変更
- `[Rename]` のパターンが空欄の場合はファイル名に何も追加せずに移動するよう変更
- ファイル名の一致判定は拡張子込みの完全一致・大文字小文字を区別しない

### 修正
- 移動先が1つも設定されていない場合にエラーログを出力して監視を開始しないよう修正

## [1.0.0] - 2025-12-23

### 追加
- FileTransferアプリケーションの初期リリース
- Windows トレイアプリケーションの基本機能を実装
- ファイル監視および自動リネーム機能
- 複数のリネームパターンに対応した設定ファイル機能
- Windows Explorer のフォルダ表示更新機能を実装
- FileRenameHandler および TrayApp の単体テスト