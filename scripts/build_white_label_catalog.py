#!/usr/bin/env python3
"""Build a white-label catalog while preserving metadata provenance boundaries."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

SCHEMA = "kafka.white-label-library.v1"
CONFIG_SCHEMA = "kafka.catalog-config.v1"
ALLOWED_AVAILABILITY = {"AVAILABLE", "UNAVAILABLE", "UNKNOWN"}
ALLOWED_FILTERS = {
    "title", "genre", "play_mode", "platform", "availability", "language", "local_tag"
}
REQUIRED_COLUMNS = {
    "title", "platform", "edition", "availability", "language",
    "local_tags", "shelf_location", "official_url"
}


def _https_or_empty(value: str, field: str) -> str:
    value = value.strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"{field} must be an https URL or empty")
    return value


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema") != CONFIG_SCHEMA:
        raise ValueError(f"config.schema must be {CONFIG_SCHEMA}")
    for field in ("catalog_id", "display_name", "locale"):
        if not isinstance(config.get(field), str) or not config[field].strip():
            raise ValueError(f"config.{field} is required")
    filters = config.get("enabled_filters", [])
    if not isinstance(filters, list) or any(item not in ALLOWED_FILTERS for item in filters):
        raise ValueError("config.enabled_filters contains an unsupported filter")
    config["contact_url"] = _https_or_empty(str(config.get("contact_url", "")), "contact_url")
    brand = config.setdefault("brand", {})
    if not isinstance(brand, dict):
        raise ValueError("config.brand must be an object")
    brand["logo_url"] = _https_or_empty(str(brand.get("logo_url", "")), "brand.logo_url")
    return config


def load_canonical(path: Path) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    canonical = json.loads(path.read_text(encoding="utf-8"))
    if canonical.get("schema") != "kafka.game-library.v1":
        raise ValueError("unsupported canonical game-library schema")
    by_title: dict[str, list[dict[str, Any]]] = {}
    for game in canonical.get("games", []):
        title = game.get("title")
        if isinstance(title, str) and title.strip():
            by_title.setdefault(title.strip().casefold(), []).append(game)
    return canonical, by_title


def load_inventory(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"inventory is missing columns: {', '.join(sorted(missing))}")
        rows: list[dict[str, str]] = []
        for number, raw in enumerate(reader, start=2):
            row = {key: (raw.get(key) or "").strip() for key in REQUIRED_COLUMNS}
            if not row["title"]:
                raise ValueError(f"row {number}: title is required")
            if row["availability"] not in ALLOWED_AVAILABILITY:
                raise ValueError(
                    f"row {number}: availability must be one of {sorted(ALLOWED_AVAILABILITY)}"
                )
            row["official_url"] = _https_or_empty(row["official_url"], f"row {number} official_url")
            rows.append(row)
    return rows


def _holding_id(catalog_id: str, row_index: int, row: dict[str, str]) -> str:
    raw = "\x1f".join(
        [catalog_id, str(row_index), row["title"], row["platform"], row["edition"]]
    ).encode("utf-8")
    return "holding-" + hashlib.sha256(raw).hexdigest()[:16]


def _official_projection(game: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "SOURCED",
        "game_id": game.get("id"),
        "title": game.get("title"),
        "release_date": game.get("release_date"),
        "developers": game.get("developers", []),
        "publishers": game.get("publishers", []),
        "official_genres": game.get("official_genres", []),
        "play_modes": game.get("play_modes", []),
        "official_store": game.get("official_store"),
        "official_website": game.get("official_website"),
        "evidence": game.get("evidence"),
    }


def build_catalog(
    canonical: dict[str, Any],
    by_title: dict[str, list[dict[str, Any]]],
    config: dict[str, Any],
    inventory: list[dict[str, str]],
) -> dict[str, Any]:
    holdings: list[dict[str, Any]] = []
    for index, row in enumerate(inventory, start=1):
        matches = by_title.get(row["title"].casefold(), [])
        game = matches[0] if len(matches) == 1 else None
        if game is None:
            official = {
                "status": "UNKNOWN", "game_id": None, "title": None, "release_date": None,
                "developers": [], "publishers": [], "official_genres": [], "play_modes": [],
                "official_store": None, "official_website": None, "evidence": None,
            }
            derived = {"status": "UNKNOWN", "design_family": None, "derived_tags": []}
            identity_status = "AMBIGUOUS_TITLE" if matches else "NOT_FOUND"
        else:
            official = _official_projection(game)
            derived = {
                "status": "DERIVED_FROM_CANONICAL_RECORD",
                "design_family": game.get("design_family"),
                "derived_tags": game.get("derived_tags", []),
            }
            identity_status = "EXACT_TITLE_UNIQUE"

        holdings.append({
            "holding_id": _holding_id(config["catalog_id"], index, row),
            "identity_status": identity_status,
            "official_metadata": official,
            "customer_inventory": {
                "title": row["title"],
                "platform": row["platform"] or "UNKNOWN",
                "edition": row["edition"] or "UNKNOWN",
                "availability": row["availability"],
                "language": row["language"] or "UNKNOWN",
                "local_tags": [x.strip() for x in row["local_tags"].split("|") if x.strip()],
                "shelf_location": row["shelf_location"] or None,
                "official_url": row["official_url"] or None,
                "provenance": "CUSTOMER_PROVIDED",
            },
            "derived_classification": derived,
        })

    return {
        "schema": SCHEMA,
        "catalog": {
            "catalog_id": config["catalog_id"],
            "display_name": config["display_name"],
            "locale": config["locale"],
            "contact_url": config["contact_url"] or None,
            "enabled_filters": config.get("enabled_filters", []),
            "brand": config.get("brand", {}),
        },
        "source": {
            "canonical_schema": canonical.get("schema"),
            "canonical_generated_at": canonical.get("generated_at"),
            "source_policy": canonical.get("ontology", {}).get("source_policy"),
        },
        "policy": {
            "availability_source": "CUSTOMER_PROVIDED_ONLY",
            "unknown_identity_is_not_inferred": True,
            "different_rows_are_not_auto_merged": True,
            "rights_statement": config.get(
                "rights_statement",
                "Game names and sourced metadata remain subject to their respective rights holders.",
            ),
        },
        "holdings": holdings,
    }


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def render_html(catalog: dict[str, Any]) -> str:
    cfg = catalog["catalog"]
    cards: list[str] = []
    for item in catalog["holdings"]:
        customer = item["customer_inventory"]
        official = item["official_metadata"]
        derived = item["derived_classification"]
        genres = official.get("official_genres") or []
        modes = official.get("play_modes") or []
        tags = customer.get("local_tags") or []
        source_url = official.get("official_store") or customer.get("official_url")

        attrs = {
            "title": customer["title"].casefold(),
            "genre": "|".join(genres).casefold(),
            "play-mode": "|".join(modes).casefold(),
            "platform": customer["platform"].casefold(),
            "availability": customer["availability"].casefold(),
            "language": customer["language"].casefold(),
            "local-tag": "|".join(tags).casefold(),
        }
        attr_text = " ".join(f'data-{key}="{_e(value)}"' for key, value in attrs.items())
        if source_url:
            source_link = f'<a href="{_e(source_url)}" rel="noopener noreferrer">公式情報を確認</a>'
        else:
            source_link = '<span class="muted">公式情報: UNKNOWN</span>'
        fields = [
            ("Platform", customer["platform"]),
            ("Edition", customer["edition"]),
            ("Language", customer["language"]),
            ("Official genres", ", ".join(genres) or "UNKNOWN"),
            ("Play modes", ", ".join(modes) or "UNKNOWN"),
            ("Derived family", derived.get("design_family") or "UNKNOWN"),
            ("Local tags", ", ".join(tags) or "—"),
            ("Shelf", customer.get("shelf_location") or "—"),
        ]
        details = "".join(f"<dt>{_e(label)}</dt><dd>{_e(value)}</dd>" for label, value in fields)
        cards.append(
            f'<article class="card" {attr_text}>'
            f'<h2>{_e(customer["title"])}</h2>'
            f'<p class="status">{_e(customer["availability"])}</p>'
            f'<dl>{details}</dl><p>{source_link}</p>'
            f'<p class="provenance">Metadata: {_e(official["status"])} / inventory: CUSTOMER_PROVIDED</p>'
            '</article>'
        )

    cta = ""
    if cfg.get("contact_url"):
        cta = f'<a class="cta" href="{_e(cfg["contact_url"])}">自分の施設の一覧を作る</a>'
    page_data = json.dumps(catalog["holdings"], ensure_ascii=False).replace("</", "<\\/")
    template = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title><style>
:root{font-family:system-ui,sans-serif;color:#181818;background:#f7f7f7}body{max-width:1120px;margin:auto;padding:24px}header{margin-bottom:24px}.controls{display:grid;grid-template-columns:2fr repeat(4,1fr);gap:10px;margin:20px 0}input,select{font:inherit;padding:10px;border:1px solid #bbb;border-radius:8px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}.card{background:white;padding:18px;border:1px solid #ddd;border-radius:12px}.card h2{font-size:1.1rem;margin-top:0}dl{display:grid;grid-template-columns:auto 1fr;gap:6px 12px}dt{font-weight:700}dd{margin:0}.status{font-weight:800}.muted,.provenance{color:#666;font-size:.9rem}.cta{display:inline-block;padding:10px 14px;border:1px solid #222;border-radius:8px;color:inherit;text-decoration:none}footer{margin-top:32px;color:#555;font-size:.9rem}@media(max-width:800px){.controls{grid-template-columns:1fr 1fr}}
</style></head><body>
<header><p class="muted">White-label library catalog</p><h1>__TITLE__</h1><p>施設の所蔵状態は施設提供データだけを表示します。ストア販売状況から在庫を推測しません。</p>__CTA__</header>
<section class="controls" aria-label="catalog filters"><input id="q" type="search" placeholder="タイトル・タグを検索"><select id="genre"><option value="">Genre: all</option></select><select id="play-mode"><option value="">Play mode: all</option></select><select id="platform"><option value="">Platform: all</option></select><select id="availability"><option value="">Availability: all</option><option>AVAILABLE</option><option>UNAVAILABLE</option><option>UNKNOWN</option></select></section>
<p id="count" aria-live="polite"></p><main class="grid">__CARDS__</main>
<footer><p>Canonical metadata snapshot: __DATE__</p><p>__RIGHTS__</p><p>公式メタデータ・顧客所蔵情報・派生分類は別レイヤーとして保持しています。</p></footer>
<script type="application/json" id="catalog-data">__DATA__</script><script>
const cards=[...document.querySelectorAll('.card')];
const controls=['genre','play-mode','platform','availability'].map(id=>document.getElementById(id));
function valuesFor(key){return [...new Set(cards.flatMap(c=>(c.dataset[key]||'').split('|')).filter(Boolean))].sort();}
for(const select of controls.slice(0,3)){for(const value of valuesFor(select.id.replace('-',''))){const o=document.createElement('option');o.value=value;o.textContent=value;select.appendChild(o);}}
const q=document.getElementById('q'),count=document.getElementById('count');
function apply(){const needle=q.value.trim().toLowerCase();let shown=0;for(const card of cards){const hay=[card.dataset.title,card.dataset.genre,card.dataset.playMode,card.dataset.platform,card.dataset.language,card.dataset.localTag].join('|');const selected=controls.every(s=>!s.value||(card.dataset[s.id.replace('-','')]||'').split('|').includes(s.value.toLowerCase()));const ok=(!needle||hay.includes(needle))&&selected;card.hidden=!ok;if(ok)shown++;}count.textContent=shown+' 件';}
q.addEventListener('input',apply);for(const c of controls)c.addEventListener('change',apply);apply();
</script></body></html>"""
    return (
        template.replace("__TITLE__", _e(cfg["display_name"]))
        .replace("__CTA__", cta)
        .replace("__CARDS__", "".join(cards))
        .replace("__DATE__", _e(catalog["source"].get("canonical_generated_at") or "UNKNOWN"))
        .replace("__RIGHTS__", _e(catalog["policy"]["rights_statement"]))
        .replace("__DATA__", page_data)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    config = load_config(args.config)
    canonical, by_title = load_canonical(args.canonical)
    inventory = load_inventory(args.inventory)
    catalog = build_catalog(canonical, by_title, config, inventory)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "index.html").write_text(render_html(catalog), encoding="utf-8")
    print(f"generated {len(catalog['holdings'])} holdings in {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
