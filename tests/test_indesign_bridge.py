from pathlib import Path
import unittest


class InDesignBridgeTests(unittest.TestCase):
    def test_script_validates_snapshot_and_preserves_release_traceability(self) -> None:
        script = (
            Path(__file__).resolve().parents[1] / "indesign/ImportPerfectCatalog.jsx"
        ).read_text(encoding="utf-8")
        self.assertIn("perfect-catalog.indesign-snapshot.v1", script)
        self.assertIn('snapshot.release.status !== "published"', script)
        self.assertIn('insertLabel("perfect_catalog_release_id"', script)
        self.assertIn('insertLabel("perfect_catalog_snapshot_sha256"', script)
        self.assertIn("card.overflows", script)
        self.assertIn("SaveOptions.NO", script)


if __name__ == "__main__":
    unittest.main()
