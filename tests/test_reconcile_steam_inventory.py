from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "reconcile_steam_inventory", ROOT / "scripts" / "reconcile_steam_inventory.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SteamInventoryReconciliationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.canonical = {
            "games": [
                {"appid": 10, "title": "Canonical A"},
                {"appid": 20, "title": "Canonical B"},
            ]
        }
        self.queue = {
            "entries": [
                {
                    "appid": 30,
                    "observed_title": "Played Game",
                    "product_kind": "game",
                    "status": "PLAYED_CONFIRMED_HOLDING_UNKNOWN",
                },
                {
                    "appid": 40,
                    "observed_title": "Overlay Tool",
                    "product_kind": "software",
                    "status": "SOFTWARE_SEPARATE",
                },
                {
                    "appid": None,
                    "observed_title": "Demo Observation",
                    "product_kind": "demo_observation",
                    "status": "VERIFY_HOLDING",
                },
            ]
        }

    def report(self, appids: list[int]) -> dict:
        payload = {
            "response": {
                "game_count": len(appids),
                "games": [{"appid": appid} for appid in appids],
            }
        }
        raw = json.dumps(payload, sort_keys=True).encode("utf-8")
        return MODULE.reconcile(payload, raw, self.canonical, self.queue)

    def test_every_difference_is_classified_or_reasoned_unknown(self) -> None:
        report = self.report([10, 30, 50])
        by_key = {(item["side"], item["appid"]): item for item in report["differences"]}

        self.assertEqual(by_key[("steam_only", 30)]["classification"], "game")
        self.assertEqual(
            by_key[("steam_only", 30)]["reason"],
            "STEAM_GET_OWNED_GAMES_CONFIRMS_OWNERSHIP",
        )
        self.assertEqual(by_key[("steam_only", 50)]["classification"], "unknown")
        self.assertEqual(
            by_key[("steam_only", 50)]["reason"],
            "NO_CANONICAL_OR_QUEUE_CLASSIFICATION",
        )
        self.assertEqual(by_key[("canonical_only", 20)]["classification"], "unknown")
        self.assertEqual(report["counts"]["unclassified_without_reason"], 0)
        self.assertEqual(report["counts"]["unknown_with_reason"], 2)

    def test_demo_software_and_play_history_remain_provenance_distinct(self) -> None:
        report = self.report([10])
        context = {item["observed_title"]: item for item in report["provenance_context"]}

        self.assertEqual(context["Played Game"]["classification"], "play-history")
        self.assertEqual(context["Overlay Tool"]["classification"], "software")
        self.assertEqual(context["Demo Observation"]["classification"], "demo")

    def test_report_contains_input_hash_but_not_raw_inventory(self) -> None:
        payload = {"response": {"game_count": 1, "games": [{"appid": 10}]}}
        raw = json.dumps(payload, sort_keys=True).encode("utf-8")
        report = MODULE.reconcile(payload, raw, self.canonical, self.queue)

        self.assertEqual(report["source"]["input_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertFalse(report["source"]["raw_input_persisted"])
        self.assertNotIn("response", report)

    def test_duplicate_or_count_mismatch_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate AppIDs"):
            MODULE.parse_owned_appids(
                {"response": {"game_count": 2, "games": [{"appid": 10}, {"appid": 10}]}}
            )
        with self.assertRaisesRegex(ValueError, "does not match"):
            MODULE.parse_owned_appids(
                {"response": {"game_count": 2, "games": [{"appid": 10}]}}
            )


if __name__ == "__main__":
    unittest.main()
