# 中小企業向け業務管理システム

<!-- markdownlint-disable MD007 MD010 MD022 MD032 MD033 MD036 MD058 MD060 -->

日報・売上・人件費・原価管理、シフト作成・出退勤打刻、教育コンテンツ管理を統合した業務管理システムです。

## 業務運用仕様（詳細）

以下の業務仕様詳細は docs 配下へ分割して管理します。

- 管理者ダッシュボード 入出金表・出力仕様: [docs/operations-spec.md#ops-spec-01](docs/operations-spec.md#ops-spec-01)
- 日報入力・人件費管理 詳細仕様: [docs/operations-spec.md#ops-spec-02](docs/operations-spec.md#ops-spec-02)
- シフト提出・作成・承認・配信フロー: [docs/operations-spec.md#ops-spec-03](docs/operations-spec.md#ops-spec-03)
- 打刻管理アプリ 仕様: [docs/operations-spec.md#ops-spec-04](docs/operations-spec.md#ops-spec-04)

## 対象


## 設計仕様書（2026年3月時点）

### 目次（設計仕様書）
- [1. システム全体像](#spec-01)
- [2. 日報管理アプリ主要機能](#spec-02)
- [3. 打刻管理アプリ主要機能](#spec-03)
- [4. 給与データ連携・損益計算](#spec-04)
- [5. データモデル（主要テーブル案）](#spec-05)
- [6. 将来的な拡張構想](#spec-06)
- [7. 監査ログポリシー（アプリ全体）](#spec-07)
- [8. ユーザーアカウント管理・ライフサイクル](#spec-08)
- [9. 時刻・タイムゾーン・月次締め基準](#spec-09)
- [10. フロントエンドセキュリティ基本方針](#spec-10)
- [11. フロントエンドセキュリティ実装タスク（MVP）](#spec-11)
- [12. バックエンドAPIセキュリティ実装タスク（MVP）](#spec-12)
- [13. セキュリティ実装 Issue 分割（起票用）](#spec-13)
- [14. 今週着手する優先3件（推奨）](#spec-14)
- [15. SEC-004 実装着手ガイド（最短）](#spec-15)
- [16. SEC-001 実装着手チェックリスト（HTTPS/Cookie）](#spec-16)
- [17. SEC-001 着手前の環境構成決定項目（最小5項目）](#spec-17)
- [18. APIレスポンス仕様（OpenAPI相当）](#spec-18)

<a id="spec-01"></a>
### 1. システム全体像
- 「日報管理アプリ」と「打刻管理アプリ」は分離（別アプリ）
- 打刻情報はDBを介して日報管理アプリに統合し、人件費計算等に活用
- 両アプリはデータ連携を前提とする

<a id="spec-02"></a>
### 2. 日報管理アプリ主要機能
- 店長・管理者のみ利用
- 店舗名選択＋店長アカウント（ユーザーID）＋パスワードで店長ログイン、管理者はGoogleアカウントでログイン
- 店舗端末（PC/iPad 等）は原則として店長専用端末とし、店舗共通パスワードは使用しない（すべての操作は店長ユーザーIDに紐づけて監査ログに記録）
- 店長は自店舗の日報記入・修正リクエスト、管理者は承認・修正
- 店長は自店舗の売上・人件費・原価率・FL比・平均客単価・新規客比率等をダッシュボードで確認
- 他店舗の売上状況もサマリーで閲覧可能
- 売上予算は管理者が設定、進捗・達成率を表示
- 小口現金管理（支給・出金・残高・月末精算）
- 掛け仕入れ管理（仕入先マスタ管理、仕入明細入力）
- 経費管理（管理者一括入力、店舗別計上、社長小口ラベル対応）
- 証憑添付（画像/PDF）、freee連携は将来的構想
- CSV/Googleスプレッドシート出力

<a id="spec-03"></a>
### 3. 打刻管理アプリ主要機能
- Web/スマホ/LINEでの打刻
- シフト提出・作成（店長・管理者が編集）
- 打刻データは日報管理アプリと連携

将来的な統合方針：
- 勤務時間の「真実のソース」は打刻データ（attendance系テーブル）とし、日報側の勤務時間は打刻データから自動集計された値を初期値とする
- 打刻漏れ・打刻ミス等に対応するため、店長および管理者に修正権限を付与する
- 店長が勤務時間を修正した場合は、必ず管理者の承認フローを通過してから確定する
- 勤務時間の修正・承認・却下のすべての操作について、誰が・いつ・どの値からどの値に変更したかを監査ログとして保存する

<a id="spec-04"></a>
### 4. 給与データ連携・損益計算
- 勤怠データを月末締め→社労士へ送付→給与計算データ（CSV）を取込
- 取込後、管理者が従業員ごとに所属店舗を配分（複数店舗勤務も対応）
- 社会保険料・雇用保険料・源泉所得税等も自動集計し、損益計算書（P/L）に反映

権限と閲覧範囲：
- 個々人の給与明細（PayrollRecord 単位）の詳細閲覧は管理者ロールのみに限定する
- 店長は自店舗に配分された人件費の「店舗別合計額」（PayrollStoreAllocation の店舗別集計）と、日別・月別の人件費サマリーのみを閲覧できる
- 店長画面からは個々の従業員名と給与明細の紐付けは表示せず、個人別の詳細金額は参照できない

<a id="spec-05"></a>
### 5. データモデル（主要テーブル案）

#### Employee（従業員）
| カラム名         | 型         | 説明                |
|------------------|------------|---------------------|
| id               | UUID/INT   | 従業員ID（主キー）  |
| name             | TEXT       | 氏名                |
| employee_code    | TEXT       | 従業員番号          |
| default_store_id | UUID/INT   | デフォルト店舗ID    |

#### Store（店舗）
| カラム名   | 型       | 説明           |
|------------|----------|----------------|
| id         | UUID/INT | 店舗ID（主キー）|
| name       | TEXT     | 店舗名         |

#### PayrollImport（給与データ取込履歴）
| カラム名        | 型         | 説明                   |
|-----------------|------------|------------------------|
| id              | UUID/INT   | 取込ID（主キー）       |
| import_date     | DATE       | 取込日                 |
| file_name       | TEXT       | 元CSVファイル名        |

#### PayrollRecord（給与明細データ）
| カラム名           | 型         | 説明                        |
|--------------------|------------|-----------------------------|
| id                 | UUID/INT   | 明細ID（主キー）            |
| payroll_import_id  | UUID/INT   | 取込履歴ID（外部キー）      |
| employee_id        | UUID/INT   | 従業員ID（外部キー）        |
| pay_month          | DATE       | 支給対象年月                |
| total_payment      | INT        | 支給合計額                  |
| health_insurance   | INT        | 健康保険料                  |
| welfare_pension    | INT        | 厚生年金保険料              |
| employment_insurance| INT       | 雇用保険料                  |
| income_tax         | INT        | 所得税                      |
| resident_tax       | INT        | 住民税                      |
| net_payment        | INT        | 差引支給額                  |

#### PayrollStoreAllocation（給与店舗配分）
| カラム名           | 型         | 説明                        |
|--------------------|------------|-----------------------------|
| id                 | UUID/INT   | 配分ID（主キー）            |
| payroll_record_id  | UUID/INT   | 給与明細ID（外部キー）      |
| store_id           | UUID/INT   | 店舗ID（外部キー）          |
| allocation_ratio   | FLOAT      | 配分比率（例: 0.5, 1.0）   |
| allocation_amount  | INT        | 配分金額                    |

**整合性ルール**
- 1つの給与明細（PayrollRecord）に紐づく全レコードの `allocation_amount` の合計は、その給与明細の `total_payment` と一致していることを必須チェックとする
- 可能であれば、同じく `allocation_ratio` の合計が 1.0（±許容誤差）になることも検証する
- 丸め誤差が発生する場合は、最終行などに差分を集約する運用とし、整合性を保つ

---

<a id="spec-06"></a>
### 6. 将来的な拡張構想
- freee API連携による証憑一括取り込み（管理者画面からボタン一つでfreeeへ送信）
- LINE打刻の本格導入
- 店舗別・期間別の高度なグラフ分析

---

<a id="spec-07"></a>
### 7. 監査ログポリシー（アプリ全体）

- 対象となる主な操作
	- ログイン/ログアウト、パスワード変更
	- ロール・権限の付与/変更/剥奪
	- 従業員・店舗・仕入先などマスタデータの追加/変更/削除（論理削除を含む）
	- 日報の登録・修正リクエスト・承認/却下
	- 勤務時間（打刻データ起点）の修正・承認/却下
	- 給与データ取込（PayrollImport）および再取込
	- 入出金表・給与関連・勤怠関連データのエクスポート操作

- 記録する情報
	- 実行ユーザーID、ユーザーロール、対象リソースID（店舗ID・従業員IDなど）
	- 操作種別（create/update/delete/approve/reject/export など）
	- 実行日時、結果（成功/失敗）、失敗時のエラー種別
	- 実行元情報（必要に応じてIPアドレスやUser-Agent など）
	- 個人情報（氏名・メールアドレス・住所・給与金額など）は監査ログには含めない

- 保持方針
	- 打刻および勤務時間修正に関するログは、人件費関連の月次締め作業と必要な監査が完了し次第削除する
	- それ以外のアプリ全体の監査ログについては、法令・社内ポリシーに従い一定期間（例：1年）保持し、その後はアーカイブまたは削除する
	- 具体的な保持期間や保管方法の詳細は docs/security.md に従い、運用設計時に確定する

---

<a id="spec-08"></a>
### 8. ユーザーアカウント管理・ライフサイクル

- アカウント種別
	- 管理者、店長、従業員、（将来）税理士ロール、社労士ロール など

- ロールごとの権限（現段階の方針）
	- 管理者
		- 全データの参照・登録・更新・削除・承認、およびエクスポートが可能
	- 店長
		- 自店舗の日報・売上・シフト・勤怠サマリーを参照・入力可能
		- 給与情報は店舗別の人件費合計のみ参照可能（個人別給与明細は参照不可）
	- 社労士ロール
		- 勤怠データ（打刻データ、シフト、勤務時間修正履歴など）および給与関連データ（PayrollImport / PayrollRecord / PayrollStoreAllocation など）を参照・エクスポート可能
		- 店長の給与計算に必要な指標（売上予算達成率・人件費率・原価率などの店舗別KPI）についても参照・エクスポート可能
		- 勤怠・給与・KPI に関しては「参照とエクスポートのみ」で、直接編集権限は付与しない
	- 税理士ロール
		- 売上・経費・小口現金・掛け仕入れ・人件費合計・P/L など「売上等に関わる会計データ」の全てを参照・エクスポート可能
		- 勤怠データ（個々の打刻やシフト詳細）にはアクセスしない前提とする
		- 会計関連データに対しては「参照とエクスポートのみ」で、直接編集権限は付与しない

- 権限設計の方針
	- 権限は「リソース（例: 勤怠・給与・売上・経費）」×「操作（参照/登録/更新/削除/承認/エクスポート）」の組み合わせで管理し、将来的に社労士・税理士ロールに対しても編集系権限を個別に付与できる設計とする
	- 現段階では社労士・税理士ロールともに編集系権限は付与せず、参照とエクスポートに限定する

- 有効/無効化
	- すべてのユーザーアカウントは `is_active` フラグを持ち、管理者は管理画面から即時に無効化（`is_active = False`）できる
	- 無効化されたアカウントはログインできず、新規トークン発行も行われない
	- 退職や契約終了が決定した時点で、管理者は当該ユーザーを即時無効化できる

- データ保持とエクスポート
	- 退職後も、社労士・税理士への報告や法定保存期間に対応するため、必要な勤怠・給与・日報・所属履歴などのデータは一定期間保持する
	- 管理者画面から、特定ユーザーに紐づく必要なデータ一式をエクスポート（例：CSV/スプレッドシート）できるようにする
	- 個人情報を含むエクスポートは管理者ロールのみが実行可能とし、将来的には税理士・社労士ロールごとに閲覧・エクスポート可能な項目を限定する

- 完全削除（物理削除）
	- docs/security.md の方針どおり、通常の削除は論理削除（`is_deleted` フラグ等）を優先する
	- 法定保存期間経過後かつ必要なデータをエクスポート済みであることを前提に、管理者はユーザーアカウントおよび関連する個人情報をDB上から完全削除（物理削除）できるようにする
	- 完全削除の実行自体は監査ログ（誰が・いつ・どのアカウントを削除したか）に記録し、個人が特定できない集計データは必要に応じてシステム内に残す

- データ保存期間（現時点の方針）
	- 日報・売上・経費・人件費データは、アプリ上で過去分を遡って確認できるよう原則無期限で保存する
	- 勤怠データ・給与データは、社労士提出後に外部エクスポートする運用を前提とし、DB保持期間は実データ量の見積もり結果を踏まえて最終確定する
	- いずれのデータも、法令要件・監査要件と矛盾しない範囲で保持・削除ポリシーを適用する

- データ容量の概算（2026年3月時点）
	- 前提条件
		- 店舗数: 3店舗
		- 従業員数: 現在11名（社員2名、アルバイト9名）/ 最大22名を想定
		- 入力頻度: 売上・買い出し・経費・掛け仕入れを毎日入力
		- 概算はテキスト系データ中心で算出し、証憑ファイル（画像/PDF）はDB外ストレージ保存を前提とする
	- 1年あたりの目安（インデックス込みの概算）
		- 日報・売上・経費・掛け仕入れ・人件費（無期限保存対象）: 約10〜15MB/年（最大規模想定で約18〜30MB/年）
		- 勤怠データ・給与データ・打刻/修正ログ: 約8〜15MB/年（最大規模想定で約15〜30MB/年）
	- 運用上の判断
		- 現在〜最大規模の範囲では、日報・売上・経費・人件費の無期限保存は現実的な容量で運用可能
		- 容量増加の主因は証憑ファイルであるため、証憑はDB本体ではなく外部ストレージで管理する

---

<a id="spec-09"></a>
### 9. 時刻・タイムゾーン・月次締め基準

- 現在の運用では、全店舗を同一タイムゾーン（日本時間 `Asia/Tokyo`）で扱う
- 日付境界は `05:00` とし、`00:00〜04:59` のデータは前日分として扱う
  - 例：3/4 02:30 の日報・打刻は、業務日付としては 3/3 扱い
- 日報の集計日付、月次締めの日付判定、給与対象月の判定はすべて同一ルール（`05:00` 境界）を適用する
- 月跨ぎ（例：4/1 03:00 退勤）のデータは前月最終日の業務として扱い、給与対象月も前月に含める
- 将来の海外店舗展開に備え、実装上は「店舗ごとのタイムゾーン設定」を追加可能な設計とする（ただし現時点では全店舗 `Asia/Tokyo` 固定）
- 将来拡張時の整合性確保のため、内部時刻はUTC保存を基本とし、表示・集計時に店舗タイムゾーンと業務日付境界（`05:00`）で変換する方針とする

<a id="spec-10"></a>
### 10. フロントエンドセキュリティ基本方針

- 通信の安全性
	- すべての画面・API通信は HTTPS を必須とする
	- HTTP アクセスは HTTPS へ強制リダイレクトし、平文通信を許可しない

- 認証Cookieの方針
	- 認証セッションは Cookie で管理し、`Secure` / `HttpOnly` / `SameSite=Lax` を基本設定とする
	- 認証情報は原則として `localStorage` に保存しない
	- 外部認証連携（Google/LINE）で要件上必要な場合のみ、限定的に Cookie ポリシーを調整する

- CSRF対策
	- 更新系リクエスト（POST/PUT/PATCH/DELETE）はすべて CSRF 対策の対象とする
	- 具体策は「SameSite=Lax の Cookie 設定」＋「CSRFトークン検証」の併用を標準とする
	- フォーム送信・API呼び出しのどちらでも同一ポリシーで検証する

- エラーハンドリング方針
	- 利用者向け画面には一般化したメッセージのみ表示し、内部構造・SQL・スタックトレース等は表示しない
	- 詳細な技術情報は内部ログのみに記録し、監査・調査時に管理者が参照する
	- 内部ログにも個人情報やトークンなどの機微情報は記録しない

- 実装難易度の目安
	- HTTPS 強制、Cookie 属性設定、一般化エラーメッセージ: 低〜中
	- CSRFトークン導入（フォーム/API一貫適用）: 中
	- 外部認証連携と厳密なCookie/CSRF制御の両立: 中〜やや高

<a id="spec-11"></a>
### 11. フロントエンドセキュリティ実装タスク（MVP）

- 優先度P0（必須）
	- HTTPS 強制
		- すべての環境で HTTP→HTTPS リダイレクトを設定する
		- 本番では HTTPS 以外のアクセスを拒否する
	- 認証Cookie設定
		- セッションCookieに `Secure=True` / `HttpOnly=True` / `SameSite=Lax` を適用する
		- 認証トークンを `localStorage` / `sessionStorage` に保存しない
	- 共通エラーハンドラ
		- 利用者向けは一般化メッセージ（例："処理に失敗しました。時間をおいて再度お試しください"）に統一する
		- 例外詳細は内部ログにのみ保存し、画面には出さない

- 優先度P1（早期対応）
	- CSRF防御
		- 更新系API（POST/PUT/PATCH/DELETE）に CSRF トークン検証を追加する
		- フォーム送信とAPI呼び出しの両方で同一ポリシーを適用する
	- セキュリティヘッダー
		- `X-Content-Type-Options: nosniff`
		- `X-Frame-Options: DENY`（必要に応じて `SAMEORIGIN`）
		- `Referrer-Policy: strict-origin-when-cross-origin`

- 優先度P2（拡張対応）
	- CSP（Content Security Policy）の段階導入
		- まずは `report-only` で違反を収集し、問題ないことを確認後に強制モードへ移行する
	- 外部認証連携の例外整理
		- Google/LINE連携で Cookie 例外が必要な場合、対象経路を限定して設定する

- 完了条件（Definition of Done）
	- HTTPS 経由以外で認証済み画面に到達できない
	- 認証Cookieに `Secure` / `HttpOnly` / `SameSite` が正しく付与されている
	- 更新系リクエストで CSRF トークン未付与時は 403 を返す
	- 500系エラー発生時、画面にスタックトレースやSQL情報が表示されない
	- セキュリティ関連の設定値・トークンがログに平文出力されない

- テスト観点（最小）
	- HTTPアクセス時に HTTPS へリダイレクトされること
	- CSRFトークンなしの POST/PUT/PATCH/DELETE が拒否されること
	- Cookie 属性（Secure/HttpOnly/SameSite）の自動テスト
	- エラー応答に内部詳細が含まれないこと

<a id="spec-12"></a>
### 12. バックエンドAPIセキュリティ実装タスク（MVP）

- 優先度P0（必須）
	- 認証ミドルウェア
		- 全ての保護対象APIで認証を必須化し、未認証は 401 を返す
		- セッション無効化済み（`is_active=False`）ユーザーのアクセスを拒否する
	- 認可（RBAC）
		- ロールごとの許可操作を API レイヤーで強制する
		- 管理者/店長/社労士/税理士の権限外アクセスは 403 を返す
	- 入力検証
		- API入力は型・必須・範囲を検証し、文字列入力は `shared.security.sanitize_input` を通す
		- SQL実行は必ずパラメータバインド（プリペアドステートメント）を使用する

- 優先度P1（早期対応）
	- 監査ログ実装
		- 重要操作（承認/却下/修正/エクスポート/権限変更）を監査ログに記録する
		- 監査ログに記録するのはユーザーID・ロール・対象ID・操作種別・結果までとし、個人情報は記録しない
	- レート制限
		- ログインAPIとトークン発行APIにレート制限を適用する
		- 一定回数失敗時の一時ロック（例: 15分）を導入する
	- エクスポート制御
		- エクスポートAPIはロール別に対象データを厳格に制限する
		- 監査目的で「誰が何をいつエクスポートしたか」を必ず記録する

- 優先度P2（拡張対応）
	- 鍵・シークレット管理の強化
		- トークン署名鍵や外部連携シークレットをセキュアストアに移行する
	- セキュリティイベント検知
		- 異常なログイン失敗や大量エクスポートを検知してアラート通知する

- 完了条件（Definition of Done）
	- 権限外アクセスに対して常に 403 が返る
	- 主要入力項目でバリデーション未通過時に 400 を返る
	- 重要操作が監査ログに欠落なく記録される
	- 個人情報・トークン・パスワードがAPIログに出力されない
	- エクスポートAPIがロール境界を越えてデータを返さない

- テスト観点（最小）
	- 未認証アクセスで 401 を返すこと
	- ロール別の許可/拒否が仕様通りであること（403 の確認）
	- 入力バリデーションとサニタイズが動作すること
	- 監査ログに必要項目が記録され、個人情報が含まれないこと
	- ログインAPIのレート制限が機能すること

<a id="spec-13"></a>
### 13. セキュリティ実装 Issue 分割（起票用）

- SEC-001: HTTPS強制とCookie属性統一（フロント）
	- 目的: HTTPを排除し、認証Cookieを安全属性で統一する
	- 範囲: HTTPSリダイレクト、`Secure/HttpOnly/SameSite=Lax` の適用確認
	- 完了条件: HTTPアクセス不可、Cookie属性が全環境で一致

- SEC-002: CSRF防御導入（フォーム/API共通）
	- 目的: 更新系リクエストの不正送信を防止する
	- 範囲: POST/PUT/PATCH/DELETE の CSRF トークン検証
	- 完了条件: トークン未付与時に 403、正常時のみ更新可

- SEC-003: 共通エラーハンドラ実装
	- 目的: 利用者向け表示から内部情報漏えいを防ぐ
	- 範囲: 一般化メッセージ、内部ログへの詳細保存、ログマスキング
	- 完了条件: 画面にスタックトレース非表示、内部ログのみ詳細保持

- SEC-004: 認証ミドルウェアと無効化アカウント遮断（バックエンド）
	- 目的: 保護対象APIを未認証・無効アカウントから防御する
	- 範囲: 認証必須化、`is_active=False` の拒否
	- 完了条件: 未認証 401、無効化ユーザーのアクセス遮断

- SEC-005: RBAC（ロール別API認可）実装
	- 目的: 管理者/店長/社労士/税理士の権限境界を強制する
	- 範囲: リソース×操作の認可判定、403 応答統一
	- 完了条件: 権限外アクセスが全て 403、権限内アクセスは許可

- SEC-006: 入力検証・サニタイズ強化
	- 目的: 不正入力・注入攻撃の入口を最小化する
	- 範囲: バリデーション、`shared.security.sanitize_input` 適用、SQLパラメータ化
	- 完了条件: 想定外入力で 400、SQL文字列連結が存在しない

- SEC-007: 監査ログ（重要操作）実装
	- 目的: 重要操作の追跡性を担保する
	- 範囲: 承認/却下/修正/権限変更/エクスポートの監査記録
	- 完了条件: 必須項目（ユーザーID/ロール/対象/結果/時刻）を欠落なく保存

- SEC-008: ログイン保護（レート制限・一時ロック）
	- 目的: 総当たり攻撃を抑止する
	- 範囲: ログインAPIとトークン発行APIのレート制限、一定回数失敗時ロック
	- 完了条件: 閾値超過時に遮断され、一定時間後に解除される

- SEC-009: エクスポートAPI権限制御
	- 目的: ロール境界を越えたデータ取得を防ぐ
	- 範囲: 管理者/社労士/税理士の対象データ制限、実行監査ログ
	- 完了条件: 仕様外データが返却されない、エクスポート操作が監査記録される

- SEC-010: セキュリティヘッダー/CSP段階導入
	- 目的: ブラウザ側保護を強化する
	- 範囲: `X-Content-Type-Options` / `X-Frame-Options` / `Referrer-Policy`、CSP `report-only`
	- 完了条件: ヘッダー付与を確認、CSP違反レポートの収集が開始される

- SEC-011: セキュリティテスト整備
	- 目的: 主要防御機能の退行を防ぐ
	- 範囲: 401/403、CSRF、Cookie属性、ログマスキング、レート制限の自動テスト
	- 完了条件: テストがCIで安定通過し、失敗時に原因特定可能

- 起票テンプレート（共通）
	- 背景 / 目的
	- スコープ（含む・含まない）
	- 実装方針
	- 完了条件（DoD）
	- テスト観点
	- セキュリティ影響（機密性・完全性・可用性）
	- 関連Issue

<a id="spec-14"></a>
### 14. 今週着手する優先3件（推奨）

- 優先1: SEC-004 認証ミドルウェアと無効化アカウント遮断
	- 理由: すべての保護APIの前提となるため。以降のRBACや監査ログの土台になる。

- 優先2: SEC-005 RBAC（ロール別API認可）実装
	- 理由: 管理者/店長/社労士/税理士の境界を早期に固定し、誤実装を防ぐため。

- 優先3: SEC-001 HTTPS強制とCookie属性統一（フロント）
	- 理由: セッション保護と盗聴対策の基本。運用環境での安全性を早期に担保するため。

- 今週対象外（次週候補）
	- SEC-011（セキュリティテスト整備）

#### 実装進捗（2026年3月4日時点）

- SEC-004 認証ミドルウェアと無効化アカウント遮断: 完了
	- 追加: `src/shared/auth.py`, `tests/test_auth.py`
	- 内容: 未認証拒否、`is_active=False` 遮断、一般化認証エラーメッセージ

- SEC-005 RBAC（ロール別API認可）実装: 完了
	- 追加: `src/shared/rbac.py`, `tests/test_rbac.py`
	- 内容: 管理者/店長/社労士/税理士ロールの認可境界を実装

- SEC-001 HTTPS強制とCookie属性統一（フロント）: 着手中
	- 状態: SEC-001設定雛形・セッション発行共通処理・疑似ログインエンドポイントまで実装済み
	- 次アクション:
		- HTTP→HTTPS リダイレクト設定
		- 認証Cookieに `Secure=True` / `HttpOnly=True` / `SameSite=Lax` を適用
		- Web Storage（localStorage / sessionStorage）への認証トークン保存禁止を実装
	- 追加: `src/shared/security_config.py`, `tests/test_security_config.py`
	- 追加: `src/shared/session.py`, `tests/test_session.py`
	- 追加: `src/shared/auth_endpoints.py`, `tests/test_auth_endpoints.py`

- SEC-002 CSRF防御導入（フォーム/API共通）: 着手中
	- 状態: CSRFトークン生成・検証ロジックを実装し、更新系疑似エンドポイントへ接続済み
	- 追加: `src/shared/csrf.py`, `tests/test_csrf.py`
	- 追加: `execute_authorized_mutation`（`src/shared/api_handlers.py`）
	- 反映: `export_sales_data`（POST）/ `replace_daily_report`（PUT）/ `update_daily_report_note`（PATCH）/ `delete_daily_report`（DELETE）へCSRF検証を接続
	- 次アクション:
		- 実フレームワーク導入時にヘッダ/Cookie抽出をミドルウェアで共通化

- SEC-007 監査ログ（重要操作）実装: 完了
	- 状態: API共通テンプレートへの監査接続、DB永続化、対象ID実連携、外部HTTP転送、Retention運用（定期実行）まで完了
	- 追加: `src/shared/audit.py`, `src/shared/tables.py`, `tests/test_audit.py`
	- 追加: `src/shared/audit_retention.py`, `scripts/run_audit_retention.py`, `tests/test_audit_retention.py`
	- 追加: `.github/workflows/audit-retention.yml`, `docs/runbook_audit_retention.md`
	- 追加: `execute_authorized_action` / `execute_authorized_mutation` の監査ログ対応（`src/shared/api_handlers.py`）
	- 反映: ユーザーID・ロール・対象ID・操作種別・結果・エラー種別の記録、機微情報キー除外
	- 反映: `business` / `attendance` 疑似エンドポイントで、業務結果の `export_id` / `report_id` / `record_id` から `target_resource_id` を監査ログへ連携
	- 次アクション:
		- Runbookに従って定期実行を継続し、Step Summary / Artifact を監査証跡として保管

- API接続テンプレート（SEC-004/005 の適用例）: 完了
	- 追加: `src/shared/api_auth.py`, `tests/test_api_auth.py`
	- 追加: `src/shared/api_handlers.py`, `tests/test_api_handlers.py`
	- 追加: `src/attendance/api.py`, `tests/test_attendance_api.py`
	- 追加: `src/business/api.py`, `tests/test_business_api.py`

- APIレスポンス仕様（OpenAPI相当）整備: 完了
	- 追加: `ATTENDANCE_SUMMARY_ENDPOINT_SPEC`（勤怠サマリー取得）
	- 追加: `EXPORT_SALES_DATA_ENDPOINT_SPEC`（売上データエクスポート）
	- 追加: `REPLACE_DAILY_REPORT_ENDPOINT_SPEC`（日報更新・PUT）
	- 追加: `UPDATE_DAILY_REPORT_NOTE_ENDPOINT_SPEC`（日報メモ更新）
	- 追加: `DELETE_DAILY_REPORT_ENDPOINT_SPEC`（日報削除・DELETE）
	- 検証: 仕様定数の必須項目テストを `tests/test_attendance_api.py` / `tests/test_business_api.py` に追加

- テスト実行結果（抜粋）
	- 認証・認可関連一式: `./.venv/bin/python -m pytest tests/test_attendance_api.py tests/test_business_api.py tests/test_api_handlers.py tests/test_api_auth.py tests/test_rbac.py tests/test_auth.py tests/test_security.py` → 55 passed
	- CSRF共通ロジック: `./.venv/bin/python -m pytest tests/test_csrf.py` → 10 passed
	- CSRF接続後の対象回帰: `./.venv/bin/python -m pytest tests/test_csrf.py tests/test_api_handlers.py tests/test_business_api.py` → 37 passed
	- API仕様定数の追加分再確認: `./.venv/bin/python -m pytest tests/test_attendance_api.py tests/test_business_api.py` → 10 passed
	- SEC-007監査ログ追加後の回帰: `./.venv/bin/python -m pytest tests/test_audit.py tests/test_api_handlers.py tests/test_business_api.py tests/test_csrf.py` → 44 passed
	- SEC-007対象ID連携・永続化反映後の回帰: `./.venv/bin/python -m pytest tests/test_api_handlers.py tests/test_business_api.py tests/test_attendance_api.py tests/test_audit.py tests/test_csrf.py` → 55 passed

#### Issue本文ドラフト（そのまま起票可）

##### SEC-004 認証ミドルウェアと無効化アカウント遮断

- 背景 / 目的
	- 保護対象APIに未認証アクセスが可能な状態を防ぐ。
	- 管理者が `is_active=False` にしたアカウントの再利用を防止する。

- スコープ（含む）
	- 保護対象APIへの認証必須化（未認証は401）
	- `is_active=False` ユーザーのアクセス拒否
	- 認証失敗時レスポンスの統一

- スコープ（含まない）
	- ロール別認可（SEC-005で対応）
	- レート制限（SEC-008で対応）

- 完了条件（DoD）
	- 未認証アクセスで 401 を返す
	- `is_active=False` ユーザーで 401 または 403 を返し、保護APIを利用できない
	- 認証エラー時のメッセージが一般化されている

- テスト観点
	- 認証あり/なしでレスポンスが正しく分岐する
	- 無効化済みユーザーでアクセス拒否される
	- ログに個人情報・トークン平文が出力されない

- 関連Issue
	- 先行: なし
	- 後続: SEC-005, SEC-007, SEC-008

##### SEC-005 RBAC（ロール別API認可）実装

- 背景 / 目的
	- 管理者/店長/社労士/税理士のデータ境界をAPIで強制し、越権アクセスを防ぐ。

- スコープ（含む）
	- リソース×操作の認可判定
	- 権限外アクセス時の 403 応答
	- エクスポートAPIのロール境界適用

- スコープ（含まない）
	- 監査ログ詳細（SEC-007で対応）
	- UIの表示制御詳細（別Issueで対応）

- 完了条件（DoD）
	- 権限外アクセスが常に 403
	- 社労士ロールは勤怠・給与・KPIのみ参照/エクスポート可
	- 税理士ロールは勤怠を除く会計データのみ参照/エクスポート可

- テスト観点
	- ロール別の許可/拒否の網羅テスト
	- エクスポートAPIの境界テスト
	- 仕様外データの返却がないこと

- 関連Issue
	- 先行: SEC-004
	- 後続: SEC-007, SEC-009, SEC-011

##### SEC-001 HTTPS強制とCookie属性統一（フロント）

- 背景 / 目的
	- セッション情報の盗聴・改ざん・スクリプト経由の窃取リスクを低減する。

- スコープ（含む）
	- HTTP→HTTPSリダイレクト設定
	- 認証Cookieの `Secure=True` / `HttpOnly=True` / `SameSite=Lax` 適用
	- 認証トークンの `localStorage` 非保存ルールの徹底

- スコープ（含まない）
	- CSRFトークン実装（SEC-002で対応）
	- CSP導入（SEC-010で対応）

- 完了条件（DoD）
	- HTTPで認証済み画面に到達できない
	- 認証Cookieの属性が要件通り
	- 開発者向け手順に設定確認方法が記載されている

- テスト観点
	- HTTPアクセス時にHTTPSへ遷移
	- Cookie属性がレスポンスヘッダに付与される
	- 認証トークンがWeb Storageに残っていない

- 関連Issue
	- 先行: なし
	- 後続: SEC-002, SEC-010

<a id="spec-15"></a>
### 15. SEC-004 実装着手ガイド（最短）

- 推奨ブランチ名
	- `feature/sec-004-auth-middleware`

- 変更対象（想定）
	- 既存更新
		- `src/shared/security.py`
		- `src/shared/exceptions.py`
		- `tests/test_security.py`
	- 新規追加（API層を見据えた共通部品）
		- `src/shared/auth.py`（認証済みユーザー解決、`is_active` 判定）
		- `tests/test_auth.py`（未認証・無効化ユーザー遮断の単体テスト）

- 実装ステップ
	- Step 1: 認証コンテキストの型を定義
		- 例: `AuthContext(user_id: str, role: str, is_active: bool)`
		- APIフレームワーク未確定でも使える純粋関数として実装する
	- Step 2: 認証必須チェック関数を実装
		- `require_authenticated_user(context: AuthContext | None) -> AuthContext`
		- `context is None` の場合は `AuthenticationError` を送出
	- Step 3: 無効化アカウント遮断関数を実装
		- `ensure_active_user(context: AuthContext) -> AuthContext`
		- `is_active=False` の場合は `AuthenticationError` を送出
	- Step 4: エラーメッセージを統一
		- 外部向け文言は「ユーザー名またはパスワードが正しくありません」等の一般化文言に統一
	- Step 5: テスト追加
		- 未認証（`None`）で例外
		- `is_active=False` で例外
		- `is_active=True` で通過

- 完了判定チェック
	- 認証チェック関数と無効化遮断関数がユニットテストで担保されている
	- 例外文言が一般化され、内部情報が露出しない
	- 後続の SEC-005（RBAC）で再利用できる関数シグネチャになっている

- ローカル確認コマンド
	- `pytest tests/test_security.py tests/test_auth.py`
	- `mypy src`
	- `ruff check src tests`

- 実装上の注意
	- APIフレームワーク未導入の段階では「ミドルウェアそのもの」よりも、ミドルウェアから呼べる純粋関数を先に固める
	- 将来 FastAPI / Flask 等を導入する際は、`src/shared/auth.py` の関数を依存注入やデコレータでラップして再利用する

<a id="spec-16"></a>
### 16. SEC-001 実装着手チェックリスト（HTTPS/Cookie）

- 推奨ブランチ名
	- `feature/sec-001-https-cookie`

- 実装タスク（チェック式）
	- [ ] 本番環境で HTTP→HTTPS リダイレクトを強制する
	- [ ] 認証Cookieに `Secure=True` を付与する
	- [ ] 認証Cookieに `HttpOnly=True` を付与する
	- [ ] 認証Cookieに `SameSite=Lax` を付与する
	- [ ] 認証トークンを `localStorage` / `sessionStorage` に保存しない設計へ統一する
	- [ ] 開発者向け確認手順（設定確認方法）をドキュメント化する

- 変更対象（候補）
	- インフラ/サーバ設定ファイル（HTTP→HTTPS リダイレクト）
	- 認証セッション発行処理（Cookie属性設定）
	- フロントエンド認証保持処理（Web Storage 非使用化）
	- `docs/security.md` の運用手順（必要に応じて補足）

- 完了条件（DoD）
	- HTTP 経由で認証済み画面へアクセスできない
	- 認証Cookieの属性が `Secure` / `HttpOnly` / `SameSite=Lax` になっている
	- 認証トークンがWeb Storageに残らない
	- 失敗時のエラーメッセージが内部情報を含まない

- テスト観点（最小）
	- [ ] HTTPアクセスでHTTPSへリダイレクトされる
	- [ ] Cookie属性がレスポンスヘッダで確認できる
	- [ ] Web Storage に認証トークンが保存されていない
	- [ ] 想定外エラー時に画面へ内部情報が表示されない

- 備考
	- 現リポジトリはAPIフレームワーク/フロント実装が未確定のため、SEC-001は環境構成の決定後に具体ファイルへ落とし込む
	- 先行して「設定値の定数化」と「テスト項目の雛形作成」から着手してもよい

<a id="spec-17"></a>
### 17. SEC-001 着手前の環境構成決定項目（最小5項目）

1. TLS終端ポイント（どこでHTTPS化するか）
	- 決めること: CDN / WAF / リバースプロキシ / アプリ本体のどこでTLS終端するか
	- 初期確定値: リバースプロキシでTLS終端し、アプリは `X-Forwarded-Proto` を信頼してHTTPS判定する

1. 本番ドメイン構成（Cookie適用範囲）
	- 決めること: `app.example.com` と `api.example.com` を分離するか、同一ドメイン配下にするか
	- 初期確定値: 同一親ドメイン配下（例: `app.<domain>` / `api.<domain>`）で運用し、`SameSite=Lax` を基本運用する

1. 認証方式とセッション保存先
	- 決めること: サーバセッション方式か、署名付きCookie方式か、セッションTTLをどうするか
	- 初期確定値: サーバセッション方式（当面はDB保存、将来Redis移行可能）＋セッションTTL 12時間＋アイドルタイムアウト 2時間

1. 外部認証（Google/LINE）コールバック要件
	- 決めること: OAuthコールバック時にCookie例外設定が必要か、必要なら対象パスをどこに限定するか
	- 初期確定値: 例外設定はコールバックパス（`/auth/google/callback`, `/auth/line/callback`）に限定し、通常画面/APIは `SameSite=Lax` を維持する

1. 環境変数とシークレット管理
	- 決めること: Cookie秘密鍵・セッション鍵・OAuthシークレットの保管場所とローテーション手順
	- 初期確定値: ローカルは `.env`、本番はシークレットマネージャを使用。鍵ローテーションは90日ごと＋漏えい疑い時は即時実施

- この確定値で実装へ落とすファイル（目安）
	- インフラ設定（HTTPSリダイレクト、プロキシヘッダー）
	- 認証セッション発行ロジック（Cookie属性、TTL）
	- OAuthコールバック処理（例外パス限定）
	- `docs/security.md`（運用手順・鍵管理の追記）

- 追加済み雛形（2026年3月4日時点）
	- `configs/security/nginx_https_reverse_proxy.conf.example`（HTTPSリダイレクト + 逆プロキシ設定例）
	- `src/shared/security_config.py`（Cookie属性・TTL・OAuthコールバックパス等の設定定義）
	- `tests/test_security_config.py`（SEC-001設定値の単体テスト）

<a id="spec-18"></a>
### 18. APIレスポンス仕様（OpenAPI相当）

- 共通レスポンス形式（`ApiResponse`）
	- 成功時
		- `status_code`: 200
		- `body`: `{ "ok": true, "data": { ... } }`
	- 失敗時
		- `status_code`: 401 / 403 / 500
		- `body`: `{ "ok": false, "error": "..." }`
	- Cookie返却が必要な認証系APIは `set_cookies` に付与情報を持たせる

- 勤怠サマリー取得API
	- 論理エンドポイント: `GET /attendance/summary`
	- 認可条件: `resource=attendance`, `action=read`
	- 仕様定数: `ATTENDANCE_SUMMARY_ENDPOINT_SPEC`
	- 代表レスポンス
		- 200: `data.total_records`, `data.resource`, `data.executed_by`
		- 401: 未認証または無効化ユーザー
		- 403: 権限不足
		- 500: 一般化エラー

- 売上データエクスポートAPI
	- 論理エンドポイント: `POST /business/sales/export`
	- 認可条件: `resource=sales`, `action=export`
	- 仕様定数: `EXPORT_SALES_DATA_ENDPOINT_SPEC`
	- 代表レスポンス
		- 200: `data.message`, `data.resource`, `data.executed_by`
		- 401: 未認証または無効化ユーザー
		- 403: 権限不足またはCSRF検証失敗
		- 500: 一般化エラー

- 日報メモ更新API
	- 論理エンドポイント: `PATCH /business/report/note`
	- 認可条件: `resource=report`, `action=update`
	- 仕様定数: `UPDATE_DAILY_REPORT_NOTE_ENDPOINT_SPEC`
	- 代表レスポンス
		- 200: `data.report_id`, `data.updated`, `data.resource`, `data.executed_by`
		- 401: 未認証または無効化ユーザー
		- 403: 権限不足またはCSRF検証失敗
		- 500: 一般化エラー

- 日報更新API（全体置換）
	- 論理エンドポイント: `PUT /business/report`
	- 認可条件: `resource=report`, `action=update`
	- 仕様定数: `REPLACE_DAILY_REPORT_ENDPOINT_SPEC`
	- 代表レスポンス
		- 200: `data.report_id`, `data.replaced`, `data.resource`, `data.executed_by`
		- 401: 未認証または無効化ユーザー
		- 403: 権限不足またはCSRF検証失敗
		- 500: 一般化エラー

- 日報削除API
	- 論理エンドポイント: `DELETE /business/report`
	- 認可条件: `resource=report`, `action=delete`
	- 仕様定数: `DELETE_DAILY_REPORT_ENDPOINT_SPEC`
	- 代表レスポンス
		- 200: `data.report_id`, `data.deleted`, `data.resource`, `data.executed_by`
		- 401: 未認証または無効化ユーザー
		- 403: 権限不足またはCSRF検証失敗
		- 500: 一般化エラー

- 実装上のルール
	- レスポンス本文の詳細は `shared.api_handlers.ApiResponse` を唯一の共通形式として扱う
	- 業務例外の詳細は外部へ返さず、500は一般化メッセージに統一する
	- 仕様変更時は、仕様定数とテストを同一PRで更新し、乖離を防ぐ

---

詳細な画面設計・API設計・運用フロー等は別途ドキュメントで管理。

## このREADMEの位置づけ

- 本ファイルは「設計仕様書（要件・ポリシー・実装方針）」の正本として扱う
- 実装時は、仕様変更を本ファイルへ先に反映してからコード変更に着手する

## 導入・開発ドキュメント

- 導入ガイド（対象/特徴/構成/クイックスタート）: [docs/README.md](docs/README.md)
- 業務運用仕様（管理者ダッシュボード/日報/シフト/打刻）: [docs/operations-spec.md](docs/operations-spec.md)
- 開発ガイド（規約/テスト/運用）: [docs/development.md](docs/development.md)
- セキュリティ・個人情報保護: [docs/security.md](docs/security.md)

## ライセンス

[LICENSE](LICENSE) を参照してください。
