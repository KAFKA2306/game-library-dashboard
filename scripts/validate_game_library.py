#!/usr/bin/env python3
"""Validate the published game-library dataset without third-party dependencies."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)+$")
ALLOWED_CONFIDENCE = {"High", "Medium", "Low", "Unknown"}


def is_http_url(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def nonempty_string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)


def validate_document(document: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(document, dict):
        return ["root: expected object"]

    if document.get("schema") != "kafka.game-library.v1":
        errors.append("schema: expected kafka.game-library.v1")
    if not isinstance(document.get("generated_at"), str) or not DATE_RE.fullmatch(document["generated_at"]):
        errors.append("generated_at: expected YYYY-MM-DD")

    games = document.get("games")
    if not isinstance(games, list):
        return errors + ["games: expected array"]
    if not games:
        errors.append("games: dataset must not be empty")

    ids: list[str] = []
    appids: list[int] = []
    for index, game in enumerate(games):
        prefix = f"games[{index}]"
        if not isinstance(game, dict):
            errors.append(f"{prefix}: expected object")
            continue

        game_id = game.get("id")
        if not isinstance(game_id, str) or not ID_RE.fullmatch(game_id):
            errors.append(f"{prefix}.id: expected stable lowercase hyphenated identifier")
        else:
            ids.append(game_id)

        title = game.get("title")
        if not isinstance(title, str) or not title.strip():
            errors.append(f"{prefix}.title: expected non-empty string")

        appid = game.get("appid")
        if appid is not None:
            if not isinstance(appid, int) or isinstance(appid, bool) or appid <= 0:
                errors.append(f"{prefix}.appid: expected positive integer or null")
            else:
                appids.append(appid)
                if isinstance(game_id, str) and game_id.startswith("steam-") and game_id != f"steam-{appid}":
                    errors.append(f"{prefix}: id/appid mismatch")

        confidence = game.get("visible_identification_confidence")
        if confidence is not None and confidence not in ALLOWED_CONFIDENCE:
            errors.append(f"{prefix}.visible_identification_confidence: unsupported value")

        for field in ("developers", "publishers", "official_genres", "play_modes", "derived_tags"):
            if field not in game or not nonempty_string_list(game[field]):
                errors.append(f"{prefix}.{field}: expected array of non-empty strings")

        if not isinstance(game.get("design_family"), str) or not game["design_family"].strip():
            errors.append(f"{prefix}.design_family: expected non-empty string")
        if not isinstance(game.get("is_free"), bool):
            errors.append(f"{prefix}.is_free: expected boolean")
        if not is_http_url(game.get("official_store")):
            errors.append(f"{prefix}.official_store: expected absolute HTTP(S) URL")
        if game.get("official_website") is not None and not is_http_url(game.get("official_website")):
            errors.append(f"{prefix}.official_website: expected HTTP(S) URL or null")
        if not is_http_url(game.get("image")):
            errors.append(f"{prefix}.image: expected absolute HTTP(S) URL")

        evidence = game.get("evidence")
        if not isinstance(evidence, dict):
            errors.append(f"{prefix}.evidence: expected object")
        else:
            for field in ("metadata_source", "store_page"):
                if not is_http_url(evidence.get(field)):
                    errors.append(f"{prefix}.evidence.{field}: expected absolute HTTP(S) URL")
            fetched_at = evidence.get("fetched_at")
            if not isinstance(fetched_at, str) or not DATE_RE.fullmatch(fetched_at):
                errors.append(f"{prefix}.evidence.fetched_at: expected YYYY-MM-DD")
            if not isinstance(evidence.get("source_type"), str) or not evidence["source_type"].strip():
                errors.append(f"{prefix}.evidence.source_type: expected non-empty string")

    for label, values in (("id", ids), ("appid", appids)):
        duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
        if duplicates:
            errors.append(f"games: duplicate {label} values: {duplicates}")

    design_families = document.get("ontology", {}).get("design_families", {})
    if isinstance(design_families, dict):
        allowed = set(design_families)
        for index, game in enumerate(games):
            if isinstance(game, dict) and game.get("design_family") not in allowed:
                errors.append(f"games[{index}].design_family: not declared in ontology.design_families")

    return errors


def build_report(path: Path, document: dict[str, object], errors: list[str]) -> dict[str, object]:
    raw = path.read_bytes()
    games = document.get("games", []) if isinstance(document, dict) else []
    return {
        "schema": "kafka.game-library.audit.v1",
        "dataset": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "record_count": len(games) if isinstance(games, list) else 0,
        "error_count": len(errors),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    try:
        document = json.loads(args.dataset.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"failed to read dataset: {exc}", file=sys.stderr)
        return 2

    errors = validate_document(document)
    report = build_report(args.dataset, document, errors)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
