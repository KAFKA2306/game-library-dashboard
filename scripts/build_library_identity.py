#!/usr/bin/env python3
"""Build and validate the Work/Edition/PlatformRelease/Holding identity layer.

The legacy game-library snapshot remains the metadata ingestion format. This module
projects it into an identity contract where Steam App IDs are external identifiers
on PlatformRelease only. Cross-record identity is allowed only through explicit
identity-links.json declarations; titles are never used as merge keys.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA = "kafka.game-library.identity.v2"
CONFIDENCE = {"VERIFIED", "CANDIDATE", "CONFLICT", "UNKNOWN"}
OWNERSHIP = {"OWNED", "MANAGED", "UNKNOWN", "NOT_OWNED"}
EDITION_STATUS = {"STANDARD", "SPECIAL", "REMASTER", "REGIONAL", "UNKNOWN"}


def _stable(prefix: str, seed: str) -> str:
    return f"{prefix}_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]}"


def _parse_release_date(original: Any, region: str) -> dict[str, Any]:
    raw = str(original or "").strip()
    if not raw:
        return {"iso": None, "precision": "unknown", "region": region, "original": raw}
    for fmt, precision in (("%b %d, %Y", "day"), ("%d %b, %Y", "day"), ("%b %Y", "month"), ("%Y", "year")):
        try:
            parsed = datetime.strptime(raw, fmt)
            if precision == "day":
                iso = parsed.date().isoformat()
            elif precision == "month":
                iso = parsed.strftime("%Y-%m")
            else:
                iso = parsed.strftime("%Y")
            return {"iso": iso, "precision": precision, "region": region, "original": raw}
        except ValueError:
            pass
    return {"iso": None, "precision": "unknown", "region": region, "original": raw}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _override_map(links: dict[str, Any]) -> dict[str, dict[str, Any]]:
    overrides: dict[str, dict[str, Any]] = {}
    for item in links.get("records", []):
        legacy_id = item.get("legacy_id")
        if not isinstance(legacy_id, str) or not legacy_id:
            raise ValueError("identity link requires non-empty legacy_id")
        if legacy_id in overrides:
            raise ValueError(f"duplicate identity link for {legacy_id}")
        overrides[legacy_id] = item
    return overrides


def build_model(legacy: dict[str, Any], links: dict[str, Any]) -> dict[str, Any]:
    games = legacy.get("games")
    if not isinstance(games, list):
        raise ValueError("legacy snapshot must contain games[]")
    overrides = _override_map(links)
    known_ids = {game.get("id") for game in games}
    unknown_links = sorted(set(overrides) - known_ids)
    if unknown_links:
        raise ValueError(f"identity links reference unknown legacy IDs: {unknown_links}")

    works: dict[str, dict[str, Any]] = {}
    editions: dict[str, dict[str, Any]] = {}
    releases: dict[str, dict[str, Any]] = {}
    holdings: dict[str, dict[str, Any]] = {}
    evidence: dict[str, dict[str, Any]] = {}
    classifications: dict[str, dict[str, Any]] = {}

    for game in games:
        legacy_id = game.get("id")
        if not isinstance(legacy_id, str) or not legacy_id:
            raise ValueError("every legacy game requires id")
        title = game.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"{legacy_id}: title is required")
        override = overrides.get(legacy_id, {})
        work_id = override.get("work_id") or _stable("work", f"legacy-record:{legacy_id}")
        edition_id = override.get("edition_id") or _stable("edition", f"{work_id}|{legacy_id}|edition")
        release_id = override.get("platform_release_id") or _stable("release", f"{edition_id}|{legacy_id}|steam")
        holding_id = override.get("holding_id") or _stable("holding", f"{release_id}|primary-library")
        confidence = override.get("identity_confidence", "VERIFIED" if game.get("visible_identification_confidence") == "High" else "CANDIDATE")
        ownership = override.get("ownership_status", "OWNED")
        edition_status = override.get("edition_status", "STANDARD")
        if confidence not in CONFIDENCE:
            raise ValueError(f"{legacy_id}: invalid identity_confidence {confidence}")
        if ownership not in OWNERSHIP:
            raise ValueError(f"{legacy_id}: invalid ownership_status {ownership}")
        if edition_status not in EDITION_STATUS:
            raise ValueError(f"{legacy_id}: invalid edition_status {edition_status}")

        source = game.get("evidence") or {}
        source_url = source.get("metadata_source") or source.get("store_page") or game.get("official_store")
        evidence_id = _stable("evidence", f"{legacy_id}|{source_url or 'unknown'}")
        evidence[evidence_id] = {
            "id": evidence_id,
            "source_url": source_url,
            "source_type": source.get("source_type", "UNKNOWN"),
            "verified_at": source.get("fetched_at"),
            "candidate_source": source.get("candidate_source"),
        }

        localized = override.get("localized_titles", {})
        work = {
            "id": work_id,
            "canonical_title": override.get("canonical_title", title),
            "localized_titles": localized,
            "identity_confidence": confidence,
            "evidence_ids": [evidence_id],
        }
        previous_work = works.get(work_id)
        if previous_work and previous_work["canonical_title"] != work["canonical_title"]:
            raise ValueError(f"{legacy_id}: shared work_id has conflicting canonical_title")
        works.setdefault(work_id, work)

        edition = {
            "id": edition_id,
            "work_id": work_id,
            "edition_name": override.get("edition_name", "Standard Edition"),
            "edition_status": edition_status,
            "release_date": _parse_release_date(game.get("release_date"), override.get("region", "GLOBAL")),
            "evidence_ids": [evidence_id],
        }
        previous_edition = editions.get(edition_id)
        if previous_edition and previous_edition["work_id"] != work_id:
            raise ValueError(f"{legacy_id}: edition_id points to multiple works")
        editions.setdefault(edition_id, edition)

        external_ids: dict[str, str] = {}
        appid = game.get("appid")
        if appid is not None:
            external_ids["steam_appid"] = str(appid)
        release = {
            "id": release_id,
            "edition_id": edition_id,
            "platform": override.get("platform", "PC"),
            "store": override.get("store", "Steam"),
            "region": override.get("region", "GLOBAL"),
            "external_ids": external_ids,
            "official_urls": {
                "store": game.get("official_store"),
                "website": game.get("official_website"),
            },
            "evidence_ids": [evidence_id],
        }
        previous_release = releases.get(release_id)
        if previous_release and previous_release != release:
            raise ValueError(f"{legacy_id}: platform_release_id is not unique")
        releases.setdefault(release_id, release)

        holding = {
            "id": holding_id,
            "platform_release_id": release_id,
            "ownership_status": ownership,
            "identity_confidence": confidence,
            "evidence_ids": [evidence_id],
        }
        if holding_id in holdings:
            raise ValueError(f"duplicate holding_id: {holding_id}")
        holdings[holding_id] = holding

        classifications.setdefault(work_id, {
            "work_id": work_id,
            "design_family": {
                "value": game.get("design_family"),
                "source": "derived",
                "revision": legacy.get("ontology", {}).get("version"),
            },
            "derived_tags": {
                "values": game.get("derived_tags", []),
                "source": "derived",
                "revision": legacy.get("ontology", {}).get("version"),
            },
        })

    model = {
        "schema": SCHEMA,
        "generated_at": legacy.get("generated_at"),
        "source_schema": legacy.get("schema"),
        "identity_policy": {
            "title_is_merge_key": False,
            "steam_appid_scope": "PlatformRelease.external_ids.steam_appid",
            "cross_record_merge_requires": "explicit identity-links.json declaration",
        },
        "works": list(works.values()),
        "editions": list(editions.values()),
        "platform_releases": list(releases.values()),
        "holdings": list(holdings.values()),
        "evidence": list(evidence.values()),
        "classifications": list(classifications.values()),
    }
    model["counts"] = validate_model(model)
    return model


def validate_model(model: dict[str, Any]) -> dict[str, int]:
    works = {item["id"]: item for item in model.get("works", [])}
    editions = {item["id"]: item for item in model.get("editions", [])}
    releases = {item["id"]: item for item in model.get("platform_releases", [])}
    evidence = {item["id"]: item for item in model.get("evidence", [])}
    holdings_list = model.get("holdings", [])
    if len(holdings_list) != len({item["id"] for item in holdings_list}):
        raise ValueError("duplicate holding IDs")
    for edition in editions.values():
        if edition["work_id"] not in works:
            raise ValueError(f"orphan edition {edition['id']}")
    for release in releases.values():
        if release["edition_id"] not in editions:
            raise ValueError(f"orphan platform release {release['id']}")
    for holding in holdings_list:
        if holding["platform_release_id"] not in releases:
            raise ValueError(f"orphan holding {holding['id']}")
        if holding["identity_confidence"] == "CONFLICT" and holding["ownership_status"] in {"OWNED", "MANAGED"}:
            raise ValueError(f"conflicted holding cannot be confirmed: {holding['id']}")
        if not holding.get("evidence_ids"):
            raise ValueError(f"holding has no evidence: {holding['id']}")
        for evidence_id in holding["evidence_ids"]:
            if evidence_id not in evidence:
                raise ValueError(f"holding references missing evidence: {holding['id']} -> {evidence_id}")
    seen_release_keys: dict[tuple[str, str, str, str], str] = {}
    for release in releases.values():
        key = (release["edition_id"], release["platform"], release["store"], release["region"])
        if key in seen_release_keys:
            raise ValueError(f"duplicate platform release semantics: {seen_release_keys[key]} and {release['id']}")
        seen_release_keys[key] = release["id"]
    return {
        "works": len(works),
        "editions": len(editions),
        "platform_releases": len(releases),
        "holdings": len(holdings_list),
    }


def duplicate_report(model: dict[str, Any]) -> dict[str, list[list[str]]]:
    editions = {item["id"]: item for item in model["editions"]}
    releases = model["platform_releases"]
    works = {item["id"]: item for item in model["works"]}
    by_title: dict[str, list[str]] = {}
    for work in works.values():
        by_title.setdefault(work["canonical_title"].casefold(), []).append(work["id"])
    same_title_different_work = [ids for ids in by_title.values() if len(set(ids)) > 1]
    work_to_editions: dict[str, list[str]] = {}
    for edition in editions.values():
        work_to_editions.setdefault(edition["work_id"], []).append(edition["id"])
    same_work_different_editions = [ids for ids in work_to_editions.values() if len(set(ids)) > 1]
    edition_to_releases: dict[str, list[str]] = {}
    for release in releases:
        edition_to_releases.setdefault(release["edition_id"], []).append(release["id"])
    same_edition_different_platforms = [ids for ids in edition_to_releases.values() if len(set(ids)) > 1]
    return {
        "same_title_different_work": same_title_different_work,
        "same_work_different_editions": same_work_different_editions,
        "same_edition_different_platforms": same_edition_different_platforms,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy", default="data/game-library.json")
    parser.add_argument("--links", default="data/identity-links.json")
    parser.add_argument("--output")
    parser.add_argument("--report")
    args = parser.parse_args()
    model = build_model(_load(Path(args.legacy)), _load(Path(args.links)))
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {"schema": model["schema"], "counts": model["counts"], "duplicates": duplicate_report(model)}
    if args.report:
        path = Path(args.report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
