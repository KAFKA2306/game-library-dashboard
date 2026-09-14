import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_catalog_delivery.py"
CANONICAL = ROOT / "data" / "game-library.json"
REVISION = "a" * 40


class CatalogDeliveryTests(unittest.TestCase):
    def _build(self, customer: str, output: Path) -> dict:
        subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--canonical",
                str(CANONICAL),
                "--delivery",
                str(ROOT / "examples" / customer / "delivery.json"),
                "--source-revision",
                REVISION,
                "--output-dir",
                str(output),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads((output / "delivery-report.json").read_text(encoding="utf-8"))

    def test_two_customer_datasets_use_same_production_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_a = self._build("customer-a", root / "a")
            report_b = self._build("customer-b", root / "b")

            self.assertEqual(report_a["status"], "PASS")
            self.assertEqual(report_b["status"], "PASS")
            self.assertEqual(report_a["source_revision"], REVISION)
            self.assertEqual(report_b["source_revision"], REVISION)
            self.assertEqual(report_a["inputs"]["inventory"]["schema"], "kafka.catalog-inventory.v1")
            self.assertNotEqual(report_a["catalog_id"], report_b["catalog_id"])
            self.assertNotEqual(
                report_a["inputs"]["inventory"]["sha256"],
                report_b["inputs"]["inventory"]["sha256"],
            )
            self.assertEqual(report_a["holding_count"], 2)
            self.assertEqual(report_b["holding_count"], 2)

    def test_same_delivery_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self._build("customer-a", root / "first")
            second = self._build("customer-a", root / "second")
            self.assertEqual(first, second)
            self.assertEqual(
                (root / "first" / "catalog.json").read_bytes(),
                (root / "second" / "catalog.json").read_bytes(),
            )
            self.assertEqual(
                (root / "first" / "index.html").read_bytes(),
                (root / "second" / "index.html").read_bytes(),
            )

    def test_invalid_source_revision_fails_before_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--canonical",
                    str(CANONICAL),
                    "--delivery",
                    str(ROOT / "examples" / "customer-a" / "delivery.json"),
                    "--source-revision",
                    "main",
                    "--output-dir",
                    str(Path(tmp) / "out"),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((Path(tmp) / "out" / "delivery-report.json").exists())


if __name__ == "__main__":
    unittest.main()
