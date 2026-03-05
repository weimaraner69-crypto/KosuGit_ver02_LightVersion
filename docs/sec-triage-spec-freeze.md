# SEC系Issueトリアージ 仕様凍結版（2026-03-05）

本ドキュメントは、SEC系Issueトリアージ運用の確定仕様を1ページに集約した凍結版です。

## 1. 対象

- 対象Issue: タイトルが `[SEC-xxx]` で始まる Issue
- 対象運用:
  - Issue作成/再オープン時の自動トリアージ
  - 週次トリアージ集計レポート
  - 未アサインIssueの警告表示と自動通知

## 2. 確定仕様

### 2-1. 自動トリアージ（Issue作成/再オープン時）

実装ファイル: `.github/workflows/sec011-issue-triage.yml`

- `issues` イベント（`opened`, `reopened`）で起動する
- タイトルが `[SEC-` で始まるIssueのみ処理する
- `security` ラベルを自動付与する
- Issue起票者がコラボレーター権限を持つ場合、起票者を assignee に自動設定する
- 自動アサイン不可時は、手動アサイン依頼コメントを投稿する

### 2-2. 週次集計レポート

実装ファイル: `.github/workflows/security-issue-triage-report.yml`

- 実行トリガー:
  - 定期実行: 毎週（UTC）
  - 手動実行: `workflow_dispatch`
- 集計対象:
  - `label:security`
  - タイトルに `SEC-` を含むIssue
- 出力:
  - Step Summary に件数サマリー（total/open/closed/assigned/unassigned）
  - Artifact にJSONレポートを保存

### 2-3. 未アサイン警告（しきい値判定）

- しきい値パラメータ: `unassigned_alert_threshold`（既定: 3）
- 判定対象: `open` かつ `no:assignee` のIssue件数
- しきい値以上のときのみ、Step Summary の警告見出しを強調表示する
- 未アサインIssue一覧は先頭に最大10件表示する

### 2-4. 自動通知コメント

- 発火条件: 未アサイン `open` 件数がしきい値以上
- 対象: 未アサイン `open` Issue 最大10件
- 通知内容:
  - report_days
  - unassigned_open_count
  - threshold
  - 担当ロール候補
    - 実装担当候補: Issue起票者
    - レビュー担当候補: リポジトリオーナー
- 重複抑止:
  - 週次マーカー `security-issue-triage-report:<ISO週>` をコメントに埋め込み
  - 同一週の同Issueへの重複投稿を抑止

## 3. 運用パラメータ（手動実行）

- `report_days`（既定: 7）
- `unassigned_alert_threshold`（既定: 3）

## 4. 凍結方針

- 当面はシンプル運用（起票者 + リポジトリオーナー候補）を標準とする
- 高度な候補自動選出（例: 直近対応者推定）は、運用課題が顕在化するまで導入しない

## 5. 変更管理

本仕様に変更が必要な場合は、以下を同一PRで更新する。

- 本ドキュメント（`docs/sec-triage-spec-freeze.md`）
- 関連ワークフロー
  - `.github/workflows/sec011-issue-triage.yml`
  - `.github/workflows/security-issue-triage-report.yml`
- 参照ドキュメント
  - `docs/development.md`
  - `README.md`
