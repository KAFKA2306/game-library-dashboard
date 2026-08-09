#!/usr/bin/env python3
"""Validate the Steam-library reconciliation queue without network access."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data" / "game-library.json"
QUEUE = ROOT / "data" / "library-sync-queue.json"
RECOMMENDATIONS = ROOT / "data" / "recommendation-candidates.json"

ALLOWED_QUEUE_STATUS = {"APPEND_READY", "VERIFY_HOLDING", "SOFTWARE_SEPARATE"}


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
    queue_appids = [entry["appid"] for entry in queue_entries]
    if len(queue_appids) != len(set(queue_appids)):
        fail("library-sync-queue.json contains duplicate appids")

    for entry in queue_entries:
        appid = entry["appid"]
        status = entry["status"]
        if status not in ALLOWED_QUEUE_STATUS:
            fail(f"appid {appid}: unsupported queue status {status}")
        check_store_url(appid, entry["official_store"])
        check_metadata_url(appid, entry["metadata_source"])

        if status == "APPEND_READY":
            if entry["product_kind"] != "game":
                fail(f"appid {appid}: APPEND_READY is only valid for games")
            if appid in canonical_appids:
                fail(f"appid {appid}: APPEND_READY already exists in canonical data; mark it merged/remove it")

        if status == "SOFTWARE_SEPARATE" and entry["product_kind"] != "software":
            fail(f"appid {appid}: SOFTWARE_SEPARATE must use product_kind=software")

        if status == "VERIFY_HOLDING" and not entry.get("holding_note"):
            fail(f"appid {appid}: VERIFY_HOLDING requires holding_note")

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
    verify_holding = sum(entry["status"] == "VERIFY_HOLDING" for entry in queue_entries)
    software = sum(entry["status"] == "SOFTWARE_SEPARATE" for entry in queue_entries)
    print(
        "library-sync audit passed: "
        f"canonical={len(canonical_appids)} "
        f"append_ready={append_ready} "
        f"verify_holding={verify_holding} "
        f"software_separate={software} "
        f"recommendations={len(recommendation_appids)}"
    )


if __name__ == "__main__":
    main()
