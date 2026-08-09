# 公開所蔵カタログ — White-label Library Catalog

## 対象

ボードゲームカフェ、ゲームサークル、研究室、コワーキング等、自ら管理するゲーム所蔵一覧をWeb公開したい運営者向けの静的カタログPoCです。

## 無料サンプル

このrepositoryには、実店舗・実顧客を名乗らない合成所蔵fixtureと、既存の正準 `data/game-library.json` を組み合わせて再生成できるサンプルを置きます。

入力:

- `catalog-config.json` — catalog ID、表示名、locale、問い合わせ先、表示filter
- `data/sample-inventory.csv` — 顧客所蔵層の合成fixture
- `data/game-library.json` — 既存の公式・出典付きメタデータ正本

生成:

```bash
python scripts/build_white_label_catalog.py \
  --canonical data/game-library.json \
  --inventory data/sample-inventory.csv \
  --config catalog-config.json \
  --output-dir build/sample-catalog
```

生成物は `catalog.json` と `index.html` です。

## データ境界

1. **Official / sourced metadata** — 既存正本で根拠があるタイトル、公式genre、play mode、公式URL、evidence。
2. **Customer-provided inventory** — platform、edition、所蔵状態、言語、施設独自tag、棚位置。
3. **Derived classification** — repositoryで既に管理しているdesign family / derived tags。

この3層は同じfieldへ上書きしません。

### 所蔵状態

`AVAILABLE | UNAVAILABLE | UNKNOWN` のみ受け付けます。Steam等の販売状況や公式サイトから、施設の「在庫あり」「貸出可」を推測しません。

### 同一性

タイトルが正準データで一意に一致した場合だけ、その公式メタデータを関連付けます。未一致・複数一致では公式genre、play mode、版、platform等を推測しません。またCSVの別行は自動統合しません。

## 権利境界

ゲーム名、画像、説明、ロゴ等の権利は各権利者に帰属します。顧客ロゴや画像を利用する場合は、顧客側で利用権を確認したassetだけを設定対象にします。MVP generatorは外部画像をダウンロード・複製しません。

## 有償PoC候補

需要検証時の範囲は、1施設・1カタログについて以下を想定します。

- 顧客CSV/JSONの列mapping
- catalog config設定
- 静的catalog生成
- 初回データ品質レビュー
- 公開手順の整備
- 更新手順の引継ぎ

価格、導入社数、来店増加、貸出率等は実績として確認できるまで表示しません。

## Privacy / measurement

営業検証用の状態は `data/catalog-funnel.json` で別々に定義します。個人情報、閲覧履歴、顧客所蔵payloadは営業analyticsへ保存しない契約です。初期値の0は実績ではありません。

## CTA

- [CSV import template](../../data/import-template.csv)
- [導入PoCを相談する](https://github.com/KAFKA2306/game-library-dashboard/issues/3)

## 保証しないこと

このカタログは在庫管理システム、貸出トランザクションシステム、権利ライセンス管理サービスではありません。公式メタデータが存在しない項目、顧客が提供していない所蔵状態、異なる版・platformの同一性を推測して補完しません。
