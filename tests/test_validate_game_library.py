import copy
import unittest

from scripts.validate_game_library import validate_document


BASE_GAME = {
    "id": "steam-123",
    "appid": 123,
    "title": "Example Game",
    "visible_identification_confidence": "High",
    "developers": ["Example Studio"],
    "publishers": ["Example Publisher"],
    "official_genres": ["Strategy"],
    "play_modes": ["solo"],
    "design_family": "systems-and-strategy",
    "derived_tags": ["strategy"],
    "is_free": False,
    "official_store": "https://store.steampowered.com/app/123/",
    "official_website": None,
    "image": "https://example.com/header.jpg",
    "evidence": {
        "metadata_source": "https://store.steampowered.com/api/appdetails?appids=123",
        "store_page": "https://store.steampowered.com/app/123/",
        "fetched_at": "2026-08-06",
        "source_type": "official_store_metadata",
    },
}


def document(*games):
    return {
        "schema": "kafka.game-library.v1",
        "generated_at": "2026-08-06",
        "ontology": {"design_families": {"systems-and-strategy": "description"}},
        "games": list(games),
    }


class ValidateGameLibraryTest(unittest.TestCase):
    def test_valid_document(self):
        self.assertEqual(validate_document(document(BASE_GAME)), [])

    def test_duplicate_identity_is_rejected(self):
        duplicate = copy.deepcopy(BASE_GAME)
        errors = validate_document(document(BASE_GAME, duplicate))
        self.assertTrue(any("duplicate id" in error for error in errors))
        self.assertTrue(any("duplicate appid" in error for error in errors))

    def test_steam_id_must_match_appid(self):
        game = copy.deepcopy(BASE_GAME)
        game["id"] = "steam-999"
        errors = validate_document(document(game))
        self.assertIn("games[0]: id/appid mismatch", errors)

    def test_unknown_design_family_is_rejected(self):
        game = copy.deepcopy(BASE_GAME)
        game["design_family"] = "undeclared-family"
        errors = validate_document(document(game))
        self.assertTrue(any("not declared" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
