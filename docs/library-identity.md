# Library identity contract

Issue #2 の同一性境界は `scripts/build_library_identity.py` が正準です。既存 `data/game-library.json` は公式メタデータを保持する ingestion snapshot として残し、そこから `kafka.game-library.identity.v2` を生成します。

## Entity boundary

- `GameWork`: 作品としての同一性。Steam AppIDを持たない。
- `GameEdition`: Standard / Special / Remaster / Regional / Unknown と、構造化した発売日を持つ。
- `PlatformRelease`: platform / store / region ごとの配信単位。Steam AppIDはここだけの `external_ids.steam_appid`。
- `LibraryHolding`: 所蔵・管理状態。必ずPlatformReleaseを参照し、そこからEdition→Workへ遡れる。
- `Evidence`: source URL、source type、検証日。Holdingから必ず参照できる。

タイトル文字列はmerge keyにしません。別legacy recordは、`data/identity-links.json` に明示した場合だけ同じWork / Editionへ束ねます。これにより同名別作品を自動統合しません。

## Steamとの境界

ValveのSteamworks公式資料では、AppはSteam上のproductの主要表現で、各Appには一意のApp IDがあります。一方、packageは一つ以上のapplications/depotsをまとめ、SKUまたはlicenseとして販売・付与される単位です。このためApp IDを作品・版・所蔵のすべてを兼ねる正準IDにはしません。

- Applications: https://partner.steamgames.com/doc/store/application
- Packages: https://partner.steamgames.com/doc/store/application/packages
- DLC: https://partner.steamgames.com/doc/store/application/dlc

## Release date

legacyの原文を捨てず、次へ分離します。

```json
{
  "iso": "2024-01-02",
  "precision": "day",
  "region": "GLOBAL",
  "original": "Jan 2, 2024"
}
```

解釈できない値は `iso=null / precision=unknown` としてfail-softに保持し、推測日を作りません。

## Derived classification

`design_family` と `derived_tags` はWork identityには使いません。生成modelでは `source=derived` と ontology revision を別に保持します。

## Validation

```bash
python -m unittest tests.test_library_identity -v
python scripts/build_library_identity.py \
  --output build/library-identity.json \
  --report build/library-identity-audit.json
```

CIは参照整合、holding/evidence traceability、duplicate holding、同一Edition+platform/store/region重複、CONFLICT所蔵の確定扱い、AppID scope、checkout cleanを検査します。

## UI

`identity.html` はWork / Edition / PlatformRelease / Holding件数を別々に算出し、Edition status / Store / Ownershipで絞り込みます。CONFLICTは通常の確定所蔵として表示しません。従来の `index.html` はmetadata-oriented viewとして残します。
