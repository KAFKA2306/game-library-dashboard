import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_white_label_catalog", ROOT / "scripts" / "build_white_label_catalog.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class WhiteLabelCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = MODULE.load_config(ROOT / "catalog-config.json")
        cls.canonical, cls.by_title = MODULE.load_canonical(ROOT / "data" / "game-library.json")
        cls.inventory = MODULE.load_inventory(ROOT / "data" / "sample-inventory.csv")
        cls.catalog = MODULE.build_catalog(cls.canonical, cls.by_title, cls.config, cls.inventory)

    def test_layers_remain_separate(self):
        first = self.catalog["holdings"][0]
        self.assertEqual(first["official_metadata"]["status"], "SOURCED")
        self.assertEqual(first["customer_inventory"]["provenance"], "CUSTOMER_PROVIDED")
        self.assertEqual(
            first["derived_classification"]["status"], "DERIVED_FROM_CANONICAL_RECORD"
        )
        self.assertNotIn("availability", first["official_metadata"])

    def test_availability_comes_only_from_customer_input(self):
        by_title = {
            row["customer_inventory"]["title"]: row for row in self.catalog["holdings"]
        }
        self.assertEqual(by_title["ALTDEUS: Beyond Chronos"]["customer_inventory"]["availability"], "AVAILABLE")
        self.assertEqual(by_title["Anno 1800"]["customer_inventory"]["availability"], "UNAVAILABLE")
        self.assertEqual(by_title["Beat Saber"]["customer_inventory"]["availability"], "UNKNOWN")

    def test_unknown_title_is_not_inferred(self):
        unknown = next(
            row for row in self.catalog["holdings"]
            if row["customer_inventory"]["title"] == "Unknown Fixture Game"
        )
        self.assertEqual(unknown["identity_status"], "NOT_FOUND")
        self.assertEqual(unknown["official_metadata"]["status"], "UNKNOWN")
        self.assertEqual(unknown["official_metadata"]["official_genres"], [])
        self.assertEqual(unknown["official_metadata"]["play_modes"], [])
        self.assertEqual(unknown["derived_classification"]["status"], "UNKNOWN")
        self.assertIsNone(unknown["derived_classification"]["design_family"])

    def test_rows_are_not_auto_merged(self):
        duplicate = dict(self.inventory[0])
        duplicate["edition"] = "Another Edition"
        duplicate["platform"] = "Another Platform"
        catalog = MODULE.build_catalog(
            self.canonical, self.by_title, self.config, [self.inventory[0], duplicate]
        )
        self.assertEqual(len(catalog["holdings"]), 2)
        self.assertNotEqual(catalog["holdings"][0]["holding_id"], catalog["holdings"][1]["holding_id"])

    def test_invalid_availability_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "inventory.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=sorted(MODULE.REQUIRED_COLUMNS))
                writer.writeheader()
                row = {key: "" for key in MODULE.REQUIRED_COLUMNS}
                row.update({"title": "Example", "availability": "YES"})
                writer.writerow(row)
            with self.assertRaises(ValueError):
                MODULE.load_inventory(path)

    def test_http_urls_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            config = dict(self.config)
            config["brand"] = dict(config.get("brand", {}))
            config["contact_url"] = "http://example.com"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaises(ValueError):
                MODULE.load_config(path)

    def test_contact_url_starts_a_qualified_inquiry(self):
        parsed = urlparse(self.config["contact_url"])
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "github.com")
        self.assertEqual(parsed.path, "/KAFKA2306/game-library-dashboard/issues/new")
        params = parse_qs(parsed.query)
        self.assertEqual(params["title"], ["施設向け公開所蔵カタログの導入相談"])
        body = params["body"][0]
        for field in (
            "施設・サークル種別:",
            "所蔵ゲーム数:",
            "現在の一覧形式（CSV / スプレッドシート / その他）:",
            "公開希望時期:",
            "相談したい内容:",
        ):
            self.assertIn(field, body)
        self.assertIn("個人情報", body)
        self.assertIn("認証情報", body)

    def test_render_contains_filters_and_provenance(self):
        rendered = MODULE.render_html(self.catalog)
        self.assertIn('type="search"', rendered)
        self.assertIn('id="availability"', rendered)
        self.assertIn("CUSTOMER_PROVIDED", rendered)
        self.assertIn("公式情報: UNKNOWN", rendered)
        self.assertIn("ストア販売状況から在庫を推測しません", rendered)
        self.assertIn("自分の施設の一覧を作る", rendered)
        self.assertIn("/issues/new?", rendered)


if __name__ == "__main__":
    unittest.main()
