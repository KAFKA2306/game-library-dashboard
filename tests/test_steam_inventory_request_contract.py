from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "data" / "steam-inventory-request-contract.json"


class SteamInventoryRequestContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_uses_official_full_inventory_endpoint(self) -> None:
        self.assertEqual(
            self.contract["endpoint"],
            "https://partner.steam-api.com/IPlayerService/GetOwnedGames/v1/",
        )
        self.assertEqual(self.contract["method"], "GET")

    def test_scope_does_not_silently_drop_free_games_or_filter_appids(self) -> None:
        self.assertEqual(
            self.contract["request_scope"],
            {
                "include_appinfo": False,
                "include_played_free_games": True,
                "appids_filter": None,
            },
        )

    def test_raw_capture_stays_in_ignored_local_boundary(self) -> None:
        self.assertEqual(self.contract["raw_response_path"], ".local/steam-owned-games.json")
        ignored = {
            line.strip()
            for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        }
        self.assertIn(".local/", ignored)

    def test_primary_sources_are_official_steamworks_docs(self) -> None:
        self.assertEqual(
            set(self.contract["primary_sources"]),
            {
                "https://partner.steamgames.com/doc/webapi/IPlayerService",
                "https://partner.steamgames.com/doc/webapi_overview/auth",
            },
        )


if __name__ == "__main__":
    unittest.main()
