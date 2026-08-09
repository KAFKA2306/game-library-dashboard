#!/usr/bin/env python3
"""Promote APPEND_READY Steam screenshot candidates into the canonical dataset.

This script intentionally does not promote PLAYED_CONFIRMED_HOLDING_UNKNOWN,
VERIFY_HOLDING, SOFTWARE_SEPARATE, or recommendation-only records.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data" / "game-library.json"
QUEUE = ROOT / "data" / "library-sync-queue.json"
TODAY = "2026-08-09"

DESIGN = {
    1225570: ("social-and-coop", ["co-op", "puzzle-platformer", "local-co-op"]),
    461040: ("social-and-coop", ["co-op", "puzzle", "party"]),
    3241660: ("social-and-coop", ["co-op", "horror", "physics"]),
    1336490: ("systems-and-strategy", ["city-builder", "roguelite", "strategy"]),
    1062090: ("systems-and-strategy", ["city-builder", "colony-sim", "automation"]),
    606150: ("action-and-adventure", ["action-rpg", "roguelite", "shopkeeping"]),
    438100: ("vr-and-embodied", ["vr", "social", "user-generated-content"]),
}

# Steam's appdetails endpoint currently does not consistently return app 461040.
# These values are taken from the official Steam Store page for that exact AppID.
PICO_FALLBACK = {
    "type": "game",
    "name": "PICO PARK:Classic Edition",
    "steam_appid": 461040,
    "is_free": None,
    "header_image": "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/461040/6f1570451e61751e3995d42fa7d7f31f90756db0/header.jpg?t=1781624101",
    "website": "http://picoparkgame.com/en/",
    "developers": ["TECOPARK"],
    "publishers": ["TECOPARK"],
    "categories": [
        {"description": "Online Co-op"},
        {"description": "Shared/Split Screen Co-op"},
        {"description": "Remote Play Together"},
    ],
    "genres": [
        {"description": "Action"},
        {"description": "Casual"},
        {"description": "Indie"},
    ],
    "release_date": {"coming_soon": False, "date": "Apr 28, 2016"},
}


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def save(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_appdetails(appid: int) -> dict:
    url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=us&l=english"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "game-library-dashboard/1.0 (+https://github.com/KAFKA2306/game-library-dashboard)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
        result = payload.get(str(appid), {})
        if result.get("success") and result.get("data"):
            return result["data"]
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        pass

    if appid == 461040:
        return PICO_FALLBACK
    raise RuntimeError(f"Steam appdetails did not return verified metadata for {appid}")


def play_modes(data: dict) -> list[str]:
    descriptions = {item.get("description", "") for item in data.get("categories", [])}
    modes: list[str] = []
    if "Single-player" in descriptions:
        modes.append("solo")
    if any("Co-op" in value for value in descriptions):
        modes.append("co-op")
    if any(
        value in descriptions
        for value in (
            "Multi-player",
            "Online PvP",
            "LAN PvP",
            "Shared/Split Screen PvP",
            "MMO",
        )
    ):
        modes.append("multiplayer")
    if any("VR" in value for value in descriptions):
        modes.append("vr")
    return modes


def build_record(entry: dict, data: dict) -> dict:
    appid = entry["appid"]
    if data.get("type") != "game" or data.get("steam_appid") != appid:
        raise RuntimeError(f"AppID {appid} did not resolve to the expected Steam game")
    if data.get("name") != entry["canonical_title"]:
        raise RuntimeError(
            f"AppID {appid} title mismatch: queue={entry['canonical_title']!r}, Steam={data.get('name')!r}"
        )

    family, tags = DESIGN[appid]
    genres = [item["description"] for item in data.get("genres", []) if item.get("description")]
    release = data.get("release_date") or {}
    return {
        "id": f"steam-{appid}",
        "appid": appid,
        "title": data["name"],
        "visible_date_from_image": "Unreadable",
        "visible_identification_confidence": "High",
        "release_date": release.get("date") or entry["release_date"],
        "coming_soon": bool(release.get("coming_soon", False)),
        "developers": data.get("developers") or [entry["developer"]],
        "publishers": data.get("publishers") or [entry["publisher"]],
        "official_genres": genres,
        "play_modes": play_modes(data),
        "design_family": family,
        "derived_tags": tags,
        "is_free": data.get("is_free"),
        "official_store": entry["official_store"],
        "official_website": data.get("website") or None,
        "image": data["header_image"],
        "image_source": (
            "Steam Store header image from official store page"
            if appid == 461040
            else "Steam CDN header image from appdetails metadata"
        ),
        "evidence": {
            "metadata_source": entry["metadata_source"],
            "store_page": entry["official_store"],
            "fetched_at": TODAY,
            "candidate_source": entry["candidate_source"],
            "source_type": "official_store_metadata",
        },
    }


def main() -> None:
    canonical = load(CANONICAL)
    queue = load(QUEUE)
    existing = {game["appid"] for game in canonical["games"]}
    ready = [entry for entry in queue["entries"] if entry["status"] == "APPEND_READY"]

    if not ready:
        print("No APPEND_READY records; canonical library already synchronized for this batch.")
        return

    new_records = []
    for entry in ready:
        appid = entry["appid"]
        if appid in existing:
            raise RuntimeError(f"APPEND_READY AppID {appid} already exists in canonical dataset")
        data = fetch_appdetails(appid)
        record = build_record(entry, data)
        new_records.append(record)
        time.sleep(0.4)

    canonical["games"].extend(new_records)
    canonical["games"].sort(key=lambda game: game["title"].casefold())
    canonical["generated_at"] = TODAY

    merged_appids = {record["appid"] for record in new_records}
    for entry in queue["entries"]:
        if entry.get("appid") in merged_appids and entry["status"] == "APPEND_READY":
            entry["status"] = "MERGED"
            entry["merged_into"] = "data/game-library.json"
            entry["merged_at"] = TODAY
    queue["status_definitions"]["MERGED"] = (
        "The screenshot candidate has been promoted into data/game-library.json after official Steam metadata verification."
    )

    save(CANONICAL, canonical)
    save(QUEUE, queue)
    print(f"Promoted {len(new_records)} records; canonical now contains {len(canonical['games'])} games.")


if __name__ == "__main__":
    main()
