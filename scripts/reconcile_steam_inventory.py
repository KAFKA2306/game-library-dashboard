#!/usr/bin/env python3
"""Reconcile a local Steam GetOwnedGames export against canonical data.

The raw Steam response is intentionally supplied as a local file and is never
written back to the repository.  The generated report contains only AppIDs,
classification/reason codes, counts, and an input SHA-256.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANONICAL = ROOT / "data" / "game-library.json"
DEFAULT_QUEUE = ROOT / "data" / "library-sync-queue.json"

CLASSIFICATIONS = {"game", "demo", "software", "tool", "DLC", "play-history", "unknown"}


def load_json_bytes(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return payload, raw


def parse_owned_appids(payload: dict[str, Any]) -> list[int]:
    response = payload.get("response")
    if not isinstance(response, dict):
        raise ValueError("Steam payload must contain object response")
    games = response.get("games")
    if games is None:
        games = []
    if not isinstance(games, list):
        raise ValueError("Steam response.games must be an array")

    appids: list[int] = []
    for index, game in enumerate(games):
        if not isinstance(game, dict):
            raise ValueError(f"Steam response.games[{index}] must be an object")
        appid = game.get("appid")
        if isinstance(appid, bool) or not isinstance(appid, int) or appid <= 0:
            raise ValueError(f"Steam response.games[{index}].appid must be a positive integer")
        appids.append(appid)

    if len(appids) != len(set(appids)):
        raise ValueError("Steam response.games contains duplicate AppIDs")

    game_count = response.get("game_count")
    if game_count is not None:
        if isinstance(game_count, bool) or not isinstance(game_count, int) or game_count < 0:
            raise ValueError("Steam response.game_count must be a non-negative integer")
        if game_count != len(appids):
            raise ValueError(
                f"Steam response.game_count={game_count} does not match games length={len(appids)}"
            )
    return sorted(appids)


def queue_index(queue: dict[str, Any]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for entry in queue.get("entries", []):
        appid = entry.get("appid")
        if appid is None:
            continue
        if appid in result:
            raise ValueError(f"queue contains duplicate AppID {appid}")
        result[appid] = entry
    return result


def classify_queue_entry(entry: dict[str, Any]) -> tuple[str, str]:
    status = entry.get("status")
    kind = entry.get("product_kind")
    if status == "SOFTWARE_SEPARATE":
        return ("tool" if kind == "tool" else "software", "QUEUE_SOFTWARE_SEPARATE")
    if status == "VERIFY_HOLDING" and kind == "demo_observation":
        return "demo", "QUEUE_DEMO_OBSERVATION"
    if status == "PLAYED_CONFIRMED_HOLDING_UNKNOWN":
        return "play-history", "QUEUE_PLAY_HISTORY_ONLY"
    if kind == "dlc":
        return "DLC", "QUEUE_DLC"
    if status in {"APPEND_READY", "MERGED"} and kind == "game":
        return "game", f"QUEUE_{status}"
    return "unknown", "QUEUE_CLASSIFICATION_UNRESOLVED"


def reconcile(
    steam_payload: dict[str, Any],
    steam_raw: bytes,
    canonical: dict[str, Any],
    queue: dict[str, Any],
) -> dict[str, Any]:
    owned = set(parse_owned_appids(steam_payload))

    canonical_games = canonical.get("games")
    if not isinstance(canonical_games, list):
        raise ValueError("canonical games must be an array")
    canonical_appids: set[int] = set()
    for index, game in enumerate(canonical_games):
        if not isinstance(game, dict):
            raise ValueError(f"canonical games[{index}] must be an object")
        appid = game.get("appid")
        if isinstance(appid, bool) or not isinstance(appid, int) or appid <= 0:
            raise ValueError(f"canonical games[{index}].appid must be a positive integer")
        if appid in canonical_appids:
            raise ValueError(f"canonical data contains duplicate AppID {appid}")
        canonical_appids.add(appid)

    qindex = queue_index(queue)
    matched = sorted(owned & canonical_appids)
    steam_only = sorted(owned - canonical_appids)
    canonical_only = sorted(canonical_appids - owned)

    differences: list[dict[str, Any]] = []
    for appid in steam_only:
        entry = qindex.get(appid)
        if entry is None:
            classification, reason = "unknown", "NO_CANONICAL_OR_QUEUE_CLASSIFICATION"
        else:
            classification, reason = classify_queue_entry(entry)
            # GetOwnedGames is explicit ownership evidence. A prior play-history-only
            # record may therefore be classified as a game in this *report* without
            # mutating the canonical dataset or queue.
            if classification == "play-history":
                classification, reason = "game", "STEAM_GET_OWNED_GAMES_CONFIRMS_OWNERSHIP"
        differences.append(
            {
                "appid": appid,
                "side": "steam_only",
                "classification": classification,
                "reason": reason,
            }
        )

    for appid in canonical_only:
        differences.append(
            {
                "appid": appid,
                "side": "canonical_only",
                "classification": "unknown",
                "reason": "CANONICAL_RECORD_NOT_IN_PROVIDED_STEAM_EXPORT",
            }
        )

    # Preserve provenance-distinct observations which intentionally may not be
    # returned by GetOwnedGames (demo/software/play history) as context records.
    context: list[dict[str, Any]] = []
    for entry in queue.get("entries", []):
        classification, reason = classify_queue_entry(entry)
        if classification not in {"demo", "software", "tool", "play-history", "DLC"}:
            continue
        appid = entry.get("appid")
        context.append(
            {
                "appid": appid,
                "observed_title": entry.get("observed_title"),
                "classification": classification,
                "reason": reason,
                "queue_status": entry.get("status"),
            }
        )

    invalid = [item for item in differences + context if item["classification"] not in CLASSIFICATIONS]
    if invalid:
        raise ValueError(f"internal error: unsupported classifications: {invalid}")
    missing_reason = [item for item in differences + context if not item.get("reason")]
    if missing_reason:
        raise ValueError("every reconciliation record must carry a reason")

    unknown_count = sum(item["classification"] == "unknown" for item in differences)
    return {
        "schema": "kafka.steam-inventory-reconciliation.v1",
        "source": {
            "kind": "Steam IPlayerService/GetOwnedGames response",
            "input_sha256": hashlib.sha256(steam_raw).hexdigest(),
            "raw_input_persisted": False,
        },
        "counts": {
            "steam_owned_appids": len(owned),
            "canonical_game_records": len(canonical_appids),
            "matched_appids": len(matched),
            "steam_only": len(steam_only),
            "canonical_only": len(canonical_only),
            "differences": len(differences),
            "unknown_with_reason": unknown_count,
            "unclassified_without_reason": 0,
        },
        "matched_appids": matched,
        "differences": sorted(differences, key=lambda item: (item["side"], item["appid"])),
        "provenance_context": sorted(
            context,
            key=lambda item: (
                item["classification"],
                -1 if item["appid"] is None else item["appid"],
                item.get("observed_title") or "",
            ),
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("steam_export", type=Path, help="local GetOwnedGames JSON response")
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    steam_payload, steam_raw = load_json_bytes(args.steam_export)
    canonical, _ = load_json_bytes(args.canonical)
    queue, _ = load_json_bytes(args.queue)
    report = reconcile(steam_payload, steam_raw, canonical, queue)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "Steam reconciliation passed: "
        f"owned={report['counts']['steam_owned_appids']} "
        f"matched={report['counts']['matched_appids']} "
        f"differences={report['counts']['differences']} "
        f"unknown_with_reason={report['counts']['unknown_with_reason']} "
        "unclassified_without_reason=0"
    )


if __name__ == "__main__":
    main()
