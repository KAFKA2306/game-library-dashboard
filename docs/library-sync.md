# Steam Library reconciliation

## Goal

The dashboard must not silently treat a screenshot, play history, a demo, Steam software, a recommendation, and a confirmed game holding as the same thing.

The Steam library screenshot observed on 2026-08-09 shows `すべてのゲーム (141)` and also exposes software/tools in other parts of the Steam UI. The canonical dataset must therefore be reconciled from evidence rather than by copying the visible counter.

A separate user statement confirmed that `Split Fiction` was played and enjoyed with the user's partner. That statement proves play history, but not ownership/current holding of the Steam app. In particular, Split Fiction supports Friend's Pass, so play history cannot be promoted to ownership evidence.

## Files

- `data/game-library.json` — current canonical verified game dataset.
- `data/library-sync-queue.json` — screenshot candidates and other explicitly sourced reconciliation states, including play-history/demo/software exceptions.
- `data/recommendation-candidates.json` — games recommended for future play; these are **not holdings**.
- `scripts/audit_library_sync.py` — deterministic, network-free consistency audit.
- `scripts/reconcile_steam_inventory.py` — diffs a local machine-readable Steam `GetOwnedGames` response against the canonical AppIDs without persisting the raw private inventory.
- `scripts/apply_library_sync.py` — promotes only `APPEND_READY` records after official Steam metadata verification.
- `.github/workflows/library-sync-audit.yml` — CI gate for the reconciliation state and reconciliation code.

## Machine-readable inventory boundary

Steam documents `IPlayerService/GetOwnedGames` as returning the games owned by a player when those details are visible to the caller:

- https://partner.steamgames.com/doc/webapi/IPlayerService
- https://partner.steamgames.com/doc/webapi_overview/auth

The endpoint requires a Web API key and SteamID. Steam's documentation also states that free games are excluded by default unless `include_played_free_games` is enabled. A full reconciliation capture must therefore use the intended complete request scope and must not use `appids_filter`.

The API key, SteamID, and raw inventory are private runtime inputs. Do **not** commit them. Store the JSON response under the ignored `.local/` directory, for example:

```text
.local/steam-owned-games.json
```

Then run the deterministic offline diff:

```bash
mkdir -p build
python scripts/reconcile_steam_inventory.py \
  .local/steam-owned-games.json \
  --output build/steam-reconciliation.json
```

The report contains only:

- SHA-256 of the exact input bytes;
- AppID counts;
- matched AppIDs;
- Steam-only and canonical-only AppID differences;
- one of `game / demo / software / tool / DLC / play-history / unknown` for each recorded difference/context item;
- a machine-readable reason for every classification, including every `unknown`.

The report never embeds the raw `response` payload, API key, SteamID, game title list, or playtime. Both `.local/` and the conventional generated report path are ignored by Git.

A `GetOwnedGames` response is ownership evidence for AppIDs contained in that response, but the reconciliation command is audit-only: it does not mutate `data/game-library.json` or silently promote queue records. An official metadata verification/promotion step remains separate.

## State model

### `APPEND_READY`

The title is visibly identified from the supplied Steam library screenshot, absent from the canonical snapshot, and its Steam Store primary metadata has been verified. It may be promoted into the canonical dataset by `scripts/apply_library_sync.py`.

### `MERGED`

The candidate passed the `APPEND_READY` boundary and has been added to `data/game-library.json`. The audit requires every `MERGED` AppID to exist in the canonical dataset.

The 2026-08-09 batch merged these seven candidates:

- Unravel Two (`1225570`)
- PICO PARK:Classic Edition (`461040`)
- R.E.P.O. (`3241660`)
- Against the Storm (`1336490`)
- Timberborn (`1062090`)
- Moonlighter (`606150`)
- VRChat (`438100`)

The application run reported `canonical=55`, `append_ready=0`, and `merged=7` after promotion. Future counts must be read from the data/CI output rather than copied into README prose.

### `PLAYED_CONFIRMED_HOLDING_UNKNOWN`

The user explicitly confirmed playing the game, but the current screenshot/inventory evidence does not establish that the Steam account owns or currently holds the app.

Current entry:

- Split Fiction (`2001120`)

This state must not be automatically promoted to `APPEND_READY` or a canonical holding. If a later machine-readable `GetOwnedGames` export contains this AppID, the reconciliation report may classify that AppID as an owned game, but the queue/canonical data still require an explicit verified promotion step.

### `VERIFY_HOLDING`

The screenshot establishes only a demo/ambiguous library item. `Backpack Battles Demo` is visible, but its demo AppID is not established by the screenshot. Therefore the paid game's AppID (`2427700`) is stored only as `related_full_game_appid`, not as the observed demo's AppID, and paid-game ownership must not be inferred.

### `SOFTWARE_SEPARATE`

Steam software/tools are tracked separately and must not inflate game counts. The screenshot visibly contains:

- XSOverlay (`1173510`)
- OVR Advanced Settings (`1009850`)

## Recommendation boundary

`A Way Out` and `LEGO Voyagers` are stored only in `data/recommendation-candidates.json` with `ownership_status=UNKNOWN`. A recommendation is never promoted to a holding without separate library evidence.

## Promotion procedure

```bash
python scripts/apply_library_sync.py
python scripts/audit_library_sync.py
```

The apply script:

1. reads only `APPEND_READY` queue entries;
2. fetches the exact AppID from the official Steam appdetails endpoint, with an official Steam Store fallback for PICO PARK:Classic Edition because that AppID is not consistently returned by appdetails;
3. rejects AppID/title/type mismatches;
4. writes official developers, publishers, genres, release data, website, image and `is_free` snapshot values;
5. writes separately versioned derived `design_family` / `derived_tags` values;
6. marks successfully promoted queue entries `MERGED`;
7. leaves play-history, demo, software and recommendation states untouched;
8. sorts the canonical library and updates `generated_at`.

## Completion criteria for full reconciliation

The screenshot counter alone is not a complete inventory export. Full reconciliation is complete only when:

1. every Steam game holding has a stable AppID/PlatformRelease identity;
2. the canonical dataset and a machine-readable Steam inventory export have been diffed;
3. screenshot evidence, user-confirmed play history, demos, tools/software, DLC, and recommendations remain provenance-distinct;
4. demos, tools/software, DLC, and recommendations are excluded from game-holding counts unless explicitly modeled as separate entities;
5. every accepted title has a primary official source and `verified_at`/`fetched_at` evidence;
6. Work / Edition / PlatformRelease / Holding boundaries from Issue #2 are preserved;
7. published counts are generated from data, not maintained as hand-written README numbers.

The code path for item 2 now exists, but the repository deliberately does not contain the user's raw Steam inventory. Therefore Issue #5 is not complete until a real, machine-readable `GetOwnedGames` export is supplied locally, reconciled, and any resulting reasoned `unknown` records are reviewed or explicitly accepted as unresolved.

## CI

Run locally:

```bash
python -m unittest tests.test_reconcile_steam_inventory -v
python scripts/audit_library_sync.py
```

The audit rejects duplicate non-null AppIDs, recommendation/holding overlap, invalid queue states, malformed Steam source URLs, software promoted as games, screenshot-free `APPEND_READY`/`MERGED` entries, unverified demo AppIDs, `APPEND_READY` entries already present in canonical data, and `MERGED` entries missing from canonical data.

The reconciliation tests additionally reject duplicate AppIDs and `game_count` mismatches, verify that every difference is either explicitly classified or a reasoned `unknown`, preserve demo/software/play-history context, and confirm that generated reports carry an input SHA-256 without embedding the raw Steam response.
