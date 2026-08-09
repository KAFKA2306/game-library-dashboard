# Game Library Dashboard — ゲーム所蔵一覧

**公開サイト:** https://kafka2306.github.io/game-library-dashboard/

公式情報で照合したゲーム情報を、静的なGitHub Pagesダッシュボードとして表示するプロジェクトです。最新件数は手書きせず `data/game-library.json` を正とします。2026-08-09に確認したSteam画面では `すべてのゲーム (141)` が表示されているため、この表示値をそのまま正準件数へ転記せず、差分監査キューで段階的に突合します。

タイトル、プラットフォーム、公式ジャンル、プレイモード、デザイン上の系統、派生タグを分けて保存し、異なる版やプラットフォームを自動的に同じ商品として統合しません。デモ、Steamソフトウェア、プレイ履歴、未所有の推薦候補も所蔵ゲームへ混ぜません。

## できること

- 所蔵ゲームを一覧表示
- タイトル、ジャンル、プレイモードで確認
- 英語・日本語表示を切り替え
- 公式メタデータと独自分類を区別
- データの出典と取得時点を保持
- GitHub Pagesで静的に公開
- Steam画面と正準データの差分を、ゲーム / デモ / ソフトウェア / プレイ履歴 / 推薦候補に分離して監査
- 一次情報確認済みの差分候補だけを正準データへ昇格
- 顧客提供の所蔵CSVから、正準メタデータと混ぜずに白ラベル静的カタログを生成

## 主なファイル

| ファイル | 内容 |
| --- | --- |
| `data/game-library.json` | ゲームライブラリの正規化済み正準スナップショット |
| `data/library-sync-queue.json` | Steam画面・ユーザー確認から得た候補を、証拠種別ごとに分離して管理する監査キュー |
| `data/recommendation-candidates.json` | 所蔵と分離した次回プレイ候補 |
| `scripts/audit_library_sync.py` | 差分キュー・推薦候補・正準データの決定論的監査 |
| `scripts/apply_library_sync.py` | `APPEND_READY` のみを公式Steam情報で再確認して正準データへ昇格 |
| `docs/library-sync.md` | Steam Library突合ルールと完了条件 |
| `index.html` | 公開ダッシュボード |
| `ontology/project.yaml` | データ取得・分類・公開の意味モデル |
| `catalog-config.json` | 白ラベルカタログの表示・導線設定 |
| `data/import-template.csv` | 顧客所蔵データの入力テンプレート |
| `scripts/build_white_label_catalog.py` | `catalog.json` / `index.html` 生成器 |
| `docs/business/white-label-library-catalog.md` | 無料sampleと導入PoCの境界 |
| `.github/workflows/` | GitHub Pages公開・検証処理 |

## Steam Library差分監査

2026-08-09のSteam画面、会話で確認できたプレイ履歴、`data/game-library.json` の正準スナップショットを区別して監査し、一次情報まで確認できた候補を `data/library-sync-queue.json` に保存しています。

2026-08-09バッチでは、Steam画面で同定でき公式情報を再確認した次の7件を `MERGED` として正準データへ追加しました。

- Unravel Two
- PICO PARK:Classic Edition
- R.E.P.O.
- Against the Storm
- Timberborn
- Moonlighter
- VRChat

そのほかの状態は分離したままです。

- `PLAYED_CONFIRMED_HOLDING_UNKNOWN`: Split Fiction — プレイ済みであることは確認済みだが、このSteamアカウントの所蔵であるとは推測しない
- `VERIFY_HOLDING`: Backpack Battles Demo — 画面からDemoのAppIDは確定できないため、有料版AppIDをDemo自身のIDとして扱わず、有料版所有も推測しない
- `SOFTWARE_SEPARATE`: XSOverlay / OVR Advanced Settings — ゲーム件数へ混ぜない
- 推薦候補: A Way Out / LEGO Voyagers — `ownership_status=UNKNOWN` のまま所蔵とは分離

画面の `141` という表示値だけから不足件数を機械的に作りません。完全突合にはSteam側の機械可読な所蔵一覧と、Issue #2で定義している Work / Edition / PlatformRelease / Holding の境界が必要です。

監査は次で実行できます。

```bash
python scripts/audit_library_sync.py
```

`APPEND_READY` を正準データへ昇格する場合は次を実行します。

```bash
python scripts/apply_library_sync.py
python scripts/audit_library_sync.py
```

CIでは `.github/workflows/library-sync-audit.yml` が整合性を検査します。

## データの情報源

- Steam Storeのアプリ情報
- Temple Gates Gamesの公開情報
- Rio Grande Gamesの公開情報
- 各タイトル・出版社の公式情報

取得元の値と、ダッシュボード上で生成した分類を混ぜません。Steam画面は候補同定にだけ使い、正式名称・AppID・開発元・発売日等は公式ストア/一次情報で再確認します。ユーザーの「プレイ済み」という確認はプレイ履歴として保存し、Steam所蔵の証拠へ自動昇格させません。

## データ処理の流れ

```text
公式サイト・ストアのメタデータ
  → タイトル・版・プラットフォームを同定
  → 表記と項目を正規化
  → デザイン系統や派生タグを追加
  → 重複・競合・欠損を判定
  → JSONデータセットを生成
  → ダッシュボードへ公開
```

Steam画面や会話からの追加候補は、直接この流れへ投入せず次の境界を通します。

```text
Steam画面 / ユーザーのプレイ確認
  → 証拠種別を保持した候補同定
  → 公式Steam AppID / Store情報で再照合
  → game / demo / software / play-history / recommendation を分離
  → library-sync queue
  → 所蔵根拠と正準schemaを満たした項目だけ game-library.json へ統合
```

## 白ラベル所蔵カタログ

`catalog-config.json` と顧客管理下のCSVを入力にすると、既存の正準データを参照する静的 `catalog.json` / `index.html` を生成できます。

```bash
python scripts/build_white_label_catalog.py \
  --canonical data/game-library.json \
  --inventory data/sample-inventory.csv \
  --config catalog-config.json \
  --output-dir build/sample-catalog
```

所蔵状態は `AVAILABLE | UNAVAILABLE | UNKNOWN` の顧客入力だけを正とし、Steam等の販売状態から施設在庫を推測しません。公式メタデータ、顧客所蔵情報、派生分類は生成JSONでも別レイヤーです。詳細は [White-label Library Catalog](docs/business/white-label-library-catalog.md) を参照してください。

## 分類の考え方

次の項目は別の意味を持ちます。

- 公式ジャンル
- 公式に示されたプレイモード
- プラットフォーム
- ゲームの版・エディション
- デザインファミリー
- システムが生成した派生タグ
- Steam画面で見えた候補
- ユーザーが確認したプレイ履歴
- 正準所蔵
- デモ / ソフトウェア
- 未所有の推薦候補

出典、取得時刻、変換規則が欠ける値は`UNKNOWN`または`flag_conflict`として扱います。

機械可読な定義:

- [プロジェクト・オントロジー](ontology/project.yaml)
- [Steam Library突合ルール](docs/library-sync.md)
- [共通因果・証拠オントロジー](https://github.com/KAFKA2306/know/blob/main/ontology/causal-evidence-core.yaml)

## ローカル確認

静的サイトのため、簡易HTTPサーバーから確認できます。

```bash
python -m http.server 8000
```

ブラウザで次を開きます。

```text
http://localhost:8000
```

## 注意

- 最新の正準件数は `data/game-library.json` を正とし、READMEへ手書きで固定しません
- Steam画面の `すべてのゲーム (141)` は突合対象の観測値であり、そのまま正準DB件数へ転記しません
- 「プレイ済み」は「このSteamアカウントが所有・所蔵している」と同義ではありません
- ストア上の配信状況、価格、対応OSは変更される可能性があります
- 同名タイトルでも版・プラットフォームが異なる場合があります
- デモ表示から有料版の所有を推測しません
- Steamソフトウェア/ツールをゲーム件数に含めません
- 推薦候補を所蔵ゲームとして扱いません
- ゲーム名、画像、説明などの権利は各権利者に帰属します
- 白ラベルsampleの所蔵状態は合成fixtureで、実店舗の在庫・貸出可否を表しません

**README最終監査:** 2026-08-09
