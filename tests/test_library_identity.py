import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_library_identity import build_model, duplicate_report, validate_model


def game(legacy_id, appid, title, release_date="Jan 2, 2024"):
    return {
        "id": legacy_id,
        "appid": appid,
        "title": title,
        "release_date": release_date,
        "visible_identification_confidence": "High",
        "official_store": f"https://store.steampowered.com/app/{appid}/",
        "official_website": None,
        "design_family": "systems-and-strategy",
        "derived_tags": ["fixture"],
        "evidence": {
            "metadata_source": f"https://store.steampowered.com/api/appdetails?appids={appid}",
            "store_page": f"https://store.steampowered.com/app/{appid}/",
            "fetched_at": "2026-08-10",
            "source_type": "official_store_metadata"
        }
    }


class LibraryIdentityTests(unittest.TestCase):
    def setUp(self):
        self.legacy = {
            "schema": "kafka.game-library.v1",
            "generated_at": "2026-08-10",
            "ontology": {"version": "test-v1"},
            "games": [
                game("steam-100", 100, "Atlas"),
                game("steam-101", 101, "Atlas Deluxe"),
                game("steam-102", 102, "Atlas"),
                game("steam-103", 103, "Atlas"),
                game("steam-104", 104, "Untitled Fixture", "2024")
            ]
        }

    def test_appid_exists_only_on_platform_release(self):
        model = build_model(self.legacy, {"records": []})
        encoded_works = json.dumps(model["works"])
        encoded_editions = json.dumps(model["editions"])
        encoded_holdings = json.dumps(model["holdings"])
        self.assertNotIn("appid", encoded_works)
        self.assertNotIn("appid", encoded_editions)
        self.assertNotIn("appid", encoded_holdings)
        self.assertEqual("100", model["platform_releases"][0]["external_ids"]["steam_appid"])

    def test_title_match_does_not_merge_distinct_records(self):
        model = build_model(self.legacy, {"records": []})
        atlas = [work for work in model["works"] if work["canonical_title"] == "Atlas"]
        self.assertEqual(3, len(atlas))
        report = duplicate_report(model)
        self.assertTrue(report["same_title_different_work"])

    def test_explicit_links_allow_same_work_different_editions_and_platforms(self):
        links = {"records": [
            {"legacy_id": "steam-100", "work_id": "work_atlas", "edition_id": "edition_atlas_standard"},
            {"legacy_id": "steam-101", "work_id": "work_atlas", "edition_id": "edition_atlas_deluxe", "edition_name": "Deluxe Edition", "edition_status": "SPECIAL"},
            {"legacy_id": "steam-102", "work_id": "work_atlas", "edition_id": "edition_atlas_standard", "platform_release_id": "release_atlas_gog", "platform": "PC", "store": "GOG"}
        ]}
        model = build_model(self.legacy, links)
        report = duplicate_report(model)
        self.assertTrue(any(set(group) == {"edition_atlas_standard", "edition_atlas_deluxe"} for group in report["same_work_different_editions"]))
        self.assertTrue(any("release_atlas_gog" in group for group in report["same_edition_different_platforms"]))

    def test_release_date_is_structured_without_discarding_original(self):
        model = build_model(self.legacy, {"records": []})
        year_only = next(item for item in model["editions"] if item["release_date"]["original"] == "2024")
        self.assertEqual("2024", year_only["release_date"]["iso"])
        self.assertEqual("year", year_only["release_date"]["precision"])
        self.assertEqual("GLOBAL", year_only["release_date"]["region"])

    def test_conflicted_holding_cannot_be_confirmed(self):
        links = {"records": [{"legacy_id": "steam-100", "identity_confidence": "CONFLICT", "ownership_status": "OWNED"}]}
        with self.assertRaisesRegex(ValueError, "conflicted holding"):
            build_model(self.legacy, links)

    def test_unknown_link_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unknown legacy IDs"):
            build_model(self.legacy, {"records": [{"legacy_id": "missing"}]})

    def test_duplicate_holding_id_fails_closed(self):
        links = {"records": [
            {"legacy_id": "steam-100", "holding_id": "holding_same"},
            {"legacy_id": "steam-101", "holding_id": "holding_same"}
        ]}
        with self.assertRaisesRegex(ValueError, "duplicate holding_id"):
            build_model(self.legacy, links)

    def test_all_holdings_trace_to_work_and_evidence(self):
        model = build_model(self.legacy, {"records": []})
        counts = validate_model(model)
        self.assertEqual(len(self.legacy["games"]), counts["holdings"])
        releases = {item["id"]: item for item in model["platform_releases"]}
        editions = {item["id"]: item for item in model["editions"]}
        works = {item["id"] for item in model["works"]}
        evidence = {item["id"] for item in model["evidence"]}
        for holding in model["holdings"]:
            release = releases[holding["platform_release_id"]]
            edition = editions[release["edition_id"]]
            self.assertIn(edition["work_id"], works)
            self.assertTrue(set(holding["evidence_ids"]).issubset(evidence))


if __name__ == "__main__":
    unittest.main()
