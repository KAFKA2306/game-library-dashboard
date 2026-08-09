#!/usr/bin/env python3
"""Validate the Steam-library reconciliation queue without network access."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data" / "game-library.json"
QUEUE = ROOT / "data" / "library-sync-queue.json"
RECOMMENDATIONS = ROOT / "data" / "recommendation-candidates.json"

ALLOWED_QUEUE_STATUS = {
    "APPEND_READY",
    "MERGED",
    "PLAYED_CONFIRMED_HOLDING_UNKNOWN",
    "VERIFY_HOLDING",
    "SOFTWARE_SEPARATE",
}


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def fail(message: str) -> None:
    raise SystemExit(f"library-sync audit failed: {message}")


def check_store_url(appid: int, url: str) -> None:
    expected = f"https://store.steampowered.com/app/{appid}/"
    if not url.startswith(expected):
        fail(f"appid {appid}: official_store must start with {expected}")


def check_metadata_url(appid: int, url: str) -> None:
    expected = f"https://store.steampowered.com/api/appdetails?appids={appid}"
    if url != expected:
        fail(f"appid {appid}: metadata_source must be {expected}")


def main() -> None:
    canonical = load(CANONICAL)
    queue = load(QUEUE)
    recommendations = load(RECOMMENDATIONS)

    canonical_appids = {game["appid"] for game in canonical["games"]}
    if len(canonical_appids) != len(canonical["games"]):
        fail("canonical game-library.json contains duplicate appids")

    queue_entries = queue["entries"]
    queue_appids = [entry["appid"] for entry in queue_entries if entry.get("appid") is not None]
    if len(queue_appids) != len(set(queue_appids)):
        fail("library-sync-queue.json contains duplicate non-null appids")

    for entry in queue_entries:
        appid = entry.get("appid")
        status = entry["status"]
        source = entry.get("candidate_source")
        if status not in ALLOWED_QUEUE_STATUS:
            fail(f"entry {entry['observed_title']}: unsupported queue status {status}")
        if not source:
            fail(f"entry {entry['observed_title']}: candidate_source is required")

        if appid is not None:
            check_store_url(appid, entry["official_store"])
            check_metadata_url(appid, entry["metadata_source"])

        if status in {"APPEND_READY", "MERGED"}:
            if appid is None:
                fail(f"entry {entry['observed_title']}: {status} requires a verified appid")
            if source != "user_supplied_steam_library_screenshot":
                fail(f"appid {appid}: {status} requires screenshot candidate evidence")
            if entry["product_kind"] != "game":
                fail(f"appid {appid}: {status} is only valid for games")

        if status == "APPEND_READY" and appid in canonical_appids:
            fail(f"appid {appid}: APPEND_READY already exists in canonical data; mark it MERGED")

        if status == "MERGED" and appid not in canonical_appids:
            fail(f"appid {appid}: MERGED must exist in canonical data")

        if status == "PLAYED_CONFIRMED_HOLDING_UNKNOWN":
            if entry["product_kind"] != "game":
                fail(f"entry {entry['observed_title']}: played-confirmed status is only valid for games")
            if source != "user_confirmed_played_in_conversation":
                fail(f"entry {entry['observed_title']}: played-confirmed status requires user confirmation provenance")
            if not entry.get("holding_note"):
                fail(f"entry {entry['observed_title']}: played-confirmed status requires holding_note")

        if status == "SOFTWARE_SEPARATE" and entry["product_kind"] != "software":
            fail(f"appid {appid}: SOFTWARE_SEPARATE must use product_kind=software")

        if status == "VERIFY_HOLDING":
            if not entry.get("holding_note"):
                fail(f"entry {entry['observed_title']}: VERIFY_HOLDING requires holding_note")
            if entry["product_kind"] == "demo_observation":
                if appid is not None:
                    fail(f"entry {entry['observed_title']}: unverified demo AppID must remain null")
                related_appid = entry.get("related_full_game_appid")
                if related_appid is None:
                    fail(f"entry {entry['observed_title']}: demo observation requires related_full_game_appid")
                check_store_url(related_appid, entry["related_full_game_store"])
                check_metadata_url(related_appid, entry["related_full_game_metadata_source"])

    recommendation_appids = []
    for candidate in recommendations["candidates"]:
        appid = candidate["appid"]
        recommendation_appids.append(appid)
        if candidate["ownership_status"] != "UNKNOWN":
            fail(f"appid {appid}: recommendation ownership must remain UNKNOWN until verified")
        official = candidate["official"]
        check_store_url(appid, official["official_store"])
        check_metadata_url(appid, official["metadata_source"])

    if len(recommendation_appids) != len(set(recommendation_appids)):
        fail("recommendation-candidates.json contains duplicate appids")

    overlap = set(queue_appids) & set(recommendation_appids)
    if overlap:
        fail(f"same appid cannot be both library-sync queue and recommendation-only candidate: {sorted(overlap)}")

    append_ready = sum(entry["status"] == "APPEND_READY" for entry in queue_entries)
    merged = sum(entry["status"] == "MERGED" for entry in queue_entries)
    played_unknown = sum(entry["status"] == "PLAYED_CONFIRMED_HOLDING_UNKNOWN" for entry in queue_entries)
    verify_holding = sum(entry["status"] == "VERIFY_HOLDING" for entry in queue_entries)
    software = sum(entry["status"] == "SOFTWARE_SEPARATE" for entry in queue_entries)
    print(
        "library-sync audit passed: "
        f"canonical={len(canonical_appids)} "
        f"append_ready={append_ready} "
        f"merged={merged} "
        f"played_holding_unknown={played_unknown} "
        f"verify_holding={verify_holding} "
        f"software_separate={software} "
        f"recommendations={len(recommendation_appids)}"
    )


if __name__ == "__main__":
    main()
