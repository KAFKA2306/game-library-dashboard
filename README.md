# Game Library Dashboard

**Steamに「141」と表示されても、それがそのまま「所有ゲーム141本」とは限らない。**

一覧にはゲーム以外のsoftwareやdemoが混ざり、プレイ済みでもそのaccountの所蔵とは限りません。推薦候補も所有物ではありません。

Game Library Dashboard は、**「見えた」「遊んだ」「持っている」を分け、公式情報で確認できた所蔵だけを自分のゲームライブラリとして扱う**静的dashboardです。

- 公開サイト: https://kafka2306.github.io/game-library-dashboard/
- 正準snapshot: `data/game-library.json`

## Vision

ゲーム一覧を「何本あるか」から、**自分がどの作品のどの版を、どのplatformで本当に所蔵しているか説明できるコレクション**へ変えます。

利用者が判断したいこと:

- このtitleは本当に所蔵しているか
- demo / software / recommendationが混ざっていないか
- プレイ済みと所有を区別できるか
- 同名作品のedition / platform releaseを分けられるか
- 画面で見つけた候補を何の証拠で正準DBへ昇格したか

## Design philosophy

- **Observed is not owned.** Steam画面で見えたことをHoldingへ自動昇格しない。
- **Played is not owned.** プレイ履歴を所蔵証拠へ変換しない。
- **Demo / software / recommendation stay separate.** 件数をきれいに合わせるためにゲーム扱いしない。
- **Work / Edition / PlatformRelease / Holdingを分ける.** 同名titleを一つのrecordへ潰さない。
- **Official metadata before merge.** 正式名称・AppID・developer・release等は公式store/一次情報で再確認する。
- **Unknown is a valid state.** 所有根拠が足りないcandidateを推測で埋めない。
- **Customer inventory and canonical metadata stay separate.** white-label catalogでも施設在庫をSteam販売状態から推測しない。

## Why / 差別化

一般的なlibrary dashboardは、APIや画面から取得した一覧をそのまま「所有ゲーム」として表示しがちです。本repoは、**所蔵という主張を候補発見から切り離し、証拠が揃ったrecordだけをcanonical Holdingへ昇格すること**を中心に置きます。

schemaやstatic Pagesが差別化なのではありません。価値は、`141`のような画面上の数字と正準所蔵数が違っても、**何が未突合で、何がdemoで、何がplay historyで、何が本当のHoldingか**を説明できることです。

## User journey

```text
Steam画面 / user observation
  → candidate
  → evidence typeを保持
  → official Steam / publisher dataで再照合
  → game / demo / software / play-history / recommendationを分離
  → sync queue
  → ownership evidenceを満たしたものだけcanonical Holdingへ
  → dashboard
```

## Current reconciliation example

2026-08-09に確認したSteam画面では `すべてのゲーム (141)` が表示されていました。この値は観測値であり、canonical countとして転記しません。

同日の監査では、公式情報まで確認できた7件を`MERGED`しました。

- Unravel Two
- PICO PARK:Classic Edition
- R.E.P.O.
- Against the Storm
- Timberborn
- Moonlighter
- VRChat

一方、次は別stateのままです。

- `PLAYED_CONFIRMED_HOLDING_UNKNOWN`: Split Fiction
- `VERIFY_HOLDING`: Backpack Battles Demo
- `SOFTWARE_SEPARATE`: XSOverlay / OVR Advanced Settings
- recommendation candidates: A Way Out / LEGO Voyagers

件数を141へ合わせるために、これらを所蔵へ昇格しません。

## Canonical model

```text
Work
  └─ Edition
       └─ PlatformRelease
            └─ Holding
```

周辺state:

```text
ObservedCandidate
PlayHistory
Demo
Software
RecommendationCandidate
```

正準データ: `data/game-library.json`

## Sync queue

`data/library-sync-queue.json` は、画面・会話等から見つかったcandidateをHoldingへ直書きしないための監査境界です。

```bash
python scripts/audit_library_sync.py
```

`APPEND_READY`だけを公式Steam情報で再確認してmerge:

```bash
python scripts/apply_library_sync.py
python scripts/audit_library_sync.py
```

詳細: [docs/library-sync.md](docs/library-sync.md)

## What you can do

- 所蔵ゲーム一覧を見る
- title / genre / play modeで確認
- 日本語 / 英語表示
- official metadataとderived classificationを区別
- source / observed timeを確認
- Steam画面との差分を証拠type別に監査
- verified candidateだけをcanonical libraryへmerge
- recommendationを所有物と分離
- customer CSVからwhite-label library catalogを生成

## White-label library catalog

顧客管理下CSVとcanonical metadataから静的catalogを生成できます。

```bash
python scripts/build_white_label_catalog.py \
  --canonical data/game-library.json \
  --inventory data/sample-inventory.csv \
  --config catalog-config.json \
  --output-dir build/sample-catalog
```

customer inventory stateは次だけを正とします。

- `AVAILABLE`
- `UNAVAILABLE`
- `UNKNOWN`

Steamの販売状況から施設在庫を推測しません。

詳細: [docs/business/white-label-library-catalog.md](docs/business/white-label-library-catalog.md)

## Evidence types

別の意味として保持するもの:

- official genre
- official play mode
- platform
- edition
- design family
- derived tag
- Steam screen observation
- user-confirmed play history
- canonical Holding
- demo / software
- recommendation candidate

source / timestamp / transformation ruleが欠ける値は`UNKNOWN`または`flag_conflict`です。

Machine-readable contracts:

- [Project ontology](ontology/project.yaml)
- [Steam reconciliation rules](docs/library-sync.md)
- [Causal/evidence core](https://github.com/KAFKA2306/know/blob/main/ontology/causal-evidence-core.yaml)

## Repository map

```text
data/game-library.json              canonical library
data/library-sync-queue.json        reconciliation candidates
data/recommendation-candidates.json recommendation-only records
scripts/audit_library_sync.py       deterministic audit
scripts/apply_library_sync.py       verified promotion
scripts/build_white_label_catalog.py catalog generation
index.html                          public dashboard
ontology/project.yaml               evidence semantics
docs/                               operating/business contracts
```

## Local preview

```bash
python -m http.server 8000
```

Open `http://localhost:8000`.

## Limits

- latest canonical countは`data/game-library.json`を優先
- Steam `141`は観測値でありcanonical countではない
- played != owned
- demo != paid-game ownership
- software/toolをgame countへ混ぜない
- recommendation != Holding
- store availability / price / OS supportは変わり得る
- sample white-label inventoryはfixtureであり実店舗在庫ではない

## Done

成功指標はSteam画面の数字とDB件数を一致させることではありません。

**新しいcandidateが増えても、「なぜこれは所蔵で、なぜこれはdemo・software・play history・recommendationのままなのか」を証拠付きで説明できること**をDoneとします。
