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
- [導入PoCを相談する](https://github.com/KAFKA2306/game-library-dashboard/issues/new?title=%E6%96%BD%E8%A8%AD%E5%90%91%E3%81%91%E5%85%AC%E9%96%8B%E6%89%80%E8%94%B5%E3%82%AB%E3%82%BF%E3%83%AD%E3%82%B0%E3%81%AE%E5%B0%8E%E5%85%A5%E7%9B%B8%E8%AB%87&body=%E5%85%AC%E9%96%8B%E5%8F%AF%E8%83%BD%E3%81%AA%E6%83%85%E5%A0%B1%E3%81%A0%E3%81%91%E3%82%92%E8%A8%98%E5%85%A5%E3%81%97%E3%81%A6%E3%81%8F%E3%81%A0%E3%81%95%E3%81%84%E3%80%82%E5%80%8B%E4%BA%BA%E6%83%85%E5%A0%B1%E3%83%BB%E9%9D%9E%E5%85%AC%E9%96%8B%E3%81%AE%E6%89%80%E8%94%B5%E3%83%87%E3%83%BC%E3%82%BF%E3%83%BB%E8%AA%8D%E8%A8%BC%E6%83%85%E5%A0%B1%E3%81%AF%E6%9B%B8%E3%81%8B%E3%81%AA%E3%81%84%E3%81%A7%E3%81%8F%E3%81%A0%E3%81%95%E3%81%84%E3%80%82%0A%0A%E6%96%BD%E8%A8%AD%E3%83%BB%E3%82%B5%E3%83%BC%E3%82%AF%E3%83%AB%E7%A8%AE%E5%88%A5%3A%0A%E6%89%80%E8%94%B5%E3%82%B2%E3%83%BC%E3%83%A0%E6%95%B0%3A%0A%E7%8F%BE%E5%9C%A8%E3%81%AE%E4%B8%80%E8%A6%A7%E5%BD%A2%E5%BC%8F%EF%BC%88CSV+%2F+%E3%82%B9%E3%83%97%E3%83%AC%E3%83%83%E3%83%89%E3%82%B7%E3%83%BC%E3%83%88+%2F+%E3%81%9D%E3%81%AE%E4%BB%96%EF%BC%89%3A%0A%E5%85%AC%E9%96%8B%E5%B8%8C%E6%9C%9B%E6%99%82%E6%9C%9F%3A%0A%E7%9B%B8%E8%AB%87%E3%81%97%E3%81%9F%E3%81%84%E5%86%85%E5%AE%B9%3A%0A)

導入相談はGitHub上の公開Issueとして作成されます。個人情報、非公開の所蔵データ、認証情報は記入しないでください。相談URLは施設・サークル種別、所蔵ゲーム数、現在の一覧形式、公開希望時期、相談内容の入力欄を事前入力します。

## 保証しないこと

このカタログは在庫管理システム、貸出トランザクションシステム、権利ライセンス管理サービスではありません。公式メタデータが存在しない項目、顧客が提供していない所蔵状態、異なる版・platformの同一性を推測して補完しません。
