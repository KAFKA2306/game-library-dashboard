#!/usr/bin/env python3
"""Build a customer catalog delivery unit through the canonical white-label generator."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import build_white_label_catalog as catalog_builder

DELIVERY_SCHEMA = "kafka.catalog-delivery.v1"
INVENTORY_SCHEMA = "kafka.catalog-inventory.v1"
REPORT_SCHEMA = "kafka.catalog-delivery-report.v1"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_customer_file(root: Path, value: str, field: str) -> Path:
    relative = Path(value)
    if relative.is_absolute():
        raise ValueError(f"{field} must be relative to the delivery spec")
    resolved_root = root.resolve()
    resolved = (root / relative).resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ValueError(f"{field} must stay inside the customer delivery directory")
    if not resolved.is_file():
        raise ValueError(f"{field} does not exist: {relative}")
    return resolved


def load_delivery_spec(path: Path) -> dict[str, Any]:
    spec = json.loads(path.read_text(encoding="utf-8"))
    if spec.get("schema") != DELIVERY_SCHEMA:
        raise ValueError(f"delivery.schema must be {DELIVERY_SCHEMA}")
    inventory = spec.get("inventory")
    if not isinstance(inventory, dict) or inventory.get("schema") != INVENTORY_SCHEMA:
        raise ValueError(f"delivery.inventory.schema must be {INVENTORY_SCHEMA}")
    if not isinstance(spec.get("config"), str) or not spec["config"].strip():
        raise ValueError("delivery.config is required")
    if not isinstance(inventory.get("path"), str) or not inventory["path"].strip():
        raise ValueError("delivery.inventory.path is required")
    return spec


def build_delivery(
    canonical_path: Path,
    delivery_spec_path: Path,
    source_revision: str,
    output_dir: Path,
) -> dict[str, Any]:
    if not SHA_RE.fullmatch(source_revision):
        raise ValueError("source_revision must be an exact lowercase 40-character commit SHA")

    spec = load_delivery_spec(delivery_spec_path)
    customer_root = delivery_spec_path.parent
    config_path = _resolve_customer_file(customer_root, spec["config"], "delivery.config")
    inventory_path = _resolve_customer_file(
        customer_root, spec["inventory"]["path"], "delivery.inventory.path"
    )

    config = catalog_builder.load_config(config_path)
    canonical, by_title = catalog_builder.load_canonical(canonical_path)
    inventory = catalog_builder.load_inventory(inventory_path)
    catalog = catalog_builder.build_catalog(canonical, by_title, config, inventory)

    output_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = output_dir / "catalog.json"
    html_path = output_dir / "index.html"
    catalog_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    html_path.write_text(catalog_builder.render_html(catalog), encoding="utf-8")

    report = {
        "schema": REPORT_SCHEMA,
        "status": "PASS",
        "source_revision": source_revision,
        "catalog_id": config["catalog_id"],
        "holding_count": len(catalog["holdings"]),
        "inputs": {
            "delivery_spec": {"schema": DELIVERY_SCHEMA, "sha256": _sha256(delivery_spec_path)},
            "config": {"schema": catalog_builder.CONFIG_SCHEMA, "sha256": _sha256(config_path)},
            "inventory": {"schema": INVENTORY_SCHEMA, "sha256": _sha256(inventory_path)},
            "canonical": {
                "schema": canonical.get("schema"),
                "sha256": _sha256(canonical_path),
            },
        },
        "outputs": {
            "catalog.json": {"sha256": _sha256(catalog_path)},
            "index.html": {"sha256": _sha256(html_path)},
        },
    }
    (output_dir / "delivery-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--delivery", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = build_delivery(
        args.canonical, args.delivery, args.source_revision, args.output_dir
    )
    print(
        f"delivery PASS: {report['catalog_id']} "
        f"({report['holding_count']} holdings) at {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
