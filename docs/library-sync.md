# Steam Library reconciliation

## Goal

The dashboard must not silently treat a screenshot, play history, a demo, Steam software, a recommendation, and a confirmed game holding as the same thing.

The Steam library screenshot observed on 2026-08-09 shows `すべてのゲーム (141)` and also exposes software/tools in other parts of the Steam UI. The canonical `data/game-library.json` snapshot was generated on 2026-06-29, so the screenshot and canonical dataset require reconciliation rather than a manual count overwrite.

A separate user statement confirmed that `Split Fiction` was played and enjoyed with the user's partner. That statement proves play history, but not ownership/current holding of the Steam app. In particular, Split Fiction supports Friend's Pass, so play history cannot be promoted to ownership evidence.

## Files

- `data/game-library.json` — current canonical verified game dataset.
- `data/library-sync-queue.json` — screenshot candidates and other explicitly sourced reconciliation states, including play-history/demo/software exceptions.
- `data/recommendation-candidates.json` — games recommended for future play; these are **not holdings**.
- `scripts/audit_library_sync.py` — deterministic, network-free consistency audit.
- `.github/workflows/library-sync-audit.yml` — CI gate for the above state.

## State model

### `APPEND_READY`

The title is visibly identified from the supplied Steam library screenshot, absent from the canonical snapshot, and its Steam Store primary metadata has been verified. It is ready for a later canonical append that supplies the full `game-library.json` schema fields.

Current append-ready candidates:

- Unravel Two (`1225570`)
- PICO PARK:Classic Edition (`461040`)
- R.E.P.O. (`3241660`)
- Against the Storm (`1336490`)
- Timberborn (`1062090`)
- Moonlighter (`606150`)
- VRChat (`438100`)

### `PLAYED_CONFIRMED_HOLDING_UNKNOWN`

The user explicitly confirmed playing the game, but the current screenshot/inventory evidence does not establish that the Steam account owns or currently holds the app.

Current entry:

- Split Fiction (`2001120`)

This state must not be automatically promoted to `APPEND_READY` or a canonical holding.

### `VERIFY_HOLDING`

The screenshot establishes only a demo/ambiguous library item. `Backpack Battles Demo` is visible, but its demo AppID is not established by the screenshot. Therefore the paid game's AppID (`2427700`) is stored only as `related_full_game_appid`, not as the observed demo's AppID, and paid-game ownership must not be inferred.

### `SOFTWARE_SEPARATE`

Steam software/tools are tracked separately and must not inflate game counts. The screenshot visibly contains:

- XSOverlay (`1173510`)
- OVR Advanced Settings (`1009850`)

## Recommendation boundary

`A Way Out` and `LEGO Voyagers` are currently stored only in `data/recommendation-candidates.json` with `ownership_status=UNKNOWN`. A recommendation is never promoted to a holding without separate library evidence.

## Completion criteria for full reconciliation

The screenshot counter alone is not a complete inventory export. Full reconciliation is complete only when:

1. every Steam game holding has a stable AppID/PlatformRelease identity;
2. the canonical dataset and a machine-readable Steam inventory export have been diffed;
3. screenshot evidence, user-confirmed play history, demos, tools/software, DLC, and recommendations remain provenance-distinct;
4. demos, tools/software, DLC, and recommendations are excluded from game-holding counts unless explicitly modeled as separate entities;
5. every accepted title has a primary official source and `verified_at` evidence;
6. Work / Edition / PlatformRelease / Holding boundaries from Issue #2 are preserved;
7. the published counts are generated from data, not maintained as hand-written README numbers.

## CI

Run locally:

```bash
python scripts/audit_library_sync.py
```

The audit rejects duplicate non-null AppIDs, recommendation/holding overlap, invalid queue states, malformed Steam source URLs, software promoted as games, screenshot-free `APPEND_READY` entries, unverified demo AppIDs, and append-ready entries that already exist in the canonical dataset.
