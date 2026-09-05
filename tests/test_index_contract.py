from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
README = ROOT / "README.md"
PRODUCTION_URL = "https://kafka2306.github.io/game-library-dashboard/"


class IndexContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = INDEX.read_text(encoding="utf-8")
        cls.readme = README.read_text(encoding="utf-8")

    def test_canonical_production_url_is_declared(self):
        self.assertIn(
            f'<link rel="canonical" href="{PRODUCTION_URL}" />',
            self.html,
        )

    def test_readme_starts_with_canonical_production_url(self):
        self.assertEqual(self.readme.splitlines()[0], PRODUCTION_URL)
        self.assertEqual(self.readme.count(PRODUCTION_URL), 1)

    def test_primary_library_precedes_secondary_analysis(self):
        self.assertLess(
            self.html.index('id="game-grid"'),
            self.html.index('class="analysis"'),
        )

    def test_filter_state_is_shareable_by_url(self):
        self.assertIn("params.set('q'", self.html)
        self.assertIn("params.get('q')", self.html)
        self.assertIn("['family', 'genre', 'mode', 'tag']", self.html)
        self.assertIn("params.set(key, controls[key].value)", self.html)
        self.assertIn("params.get(key)", self.html)
        self.assertIn("history.replaceState", self.html)

    def test_compare_state_is_shareable_and_bounded(self):
        self.assertIn('id="compare-panel"', self.html)
        self.assertIn('aria-live="polite"', self.html)
        self.assertIn("params.set('compare', compareIds.join(','))", self.html)
        self.assertIn("get('compare')", self.html)
        self.assertIn(".slice(0, 2)", self.html)
        self.assertIn("compareIds.length < 2", self.html)
        self.assertIn('data-compare-id=', self.html)
        self.assertIn('aria-pressed="false"', self.html)

    def test_compare_uses_existing_canonical_fields(self):
        for field in ("release_date", "design_family", "play_modes", "official_genres", "derived_tags", "official_store", "metadata_source"):
            self.assertIn(f"game.{field}", self.html)

    def test_data_fetch_failure_is_not_silently_swallowed(self):
        self.assertIn("if (!response.ok) throw new Error", self.html)
        self.assertIn("UNVERIFIED:", self.html)
        self.assertIn("throw error", self.html)

    def test_design_foundation_values_are_used(self):
        for token in ("#F7F5EF", "#FFFFFF", "#17233F", "#667085", "#D9D6CE", "#2563EB"):
            self.assertIn(token, self.html)


if __name__ == "__main__":
    unittest.main()
