from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PendingMigrationUpdaterTests(unittest.TestCase):
    def test_single_public_updater_detects_each_optional_schema_block(self) -> None:
        sql = (ROOT / "db/bootstrap/apply_pending_migrations.sql").read_text(encoding="utf-8")
        self.assertIn("to_regclass('perfect_catalog.import_plan')", sql)
        for version in range(7, 23):
            self.assertIn(f"../migrations/{version:04d}_", sql)
        self.assertIn("information_schema.columns", sql)
        self.assertIn("\\quit 3", sql)
        self.assertIn("checksum_0017", sql)
        self.assertIn("checksum_0018", sql)
        self.assertIn("checksum_0021", sql)
        self.assertIn("checksum_0022", sql)
        self.assertIn("apply_controlled_product_update", sql)
        self.assertIn("MIGRATION_PENDING", sql)
        self.assertIn("SCHEMA_AHEAD_OF_LEDGER", sql)
        self.assertIn("CHECKSUM_MISMATCH", sql)

    def test_root_exposes_one_migration_entrypoint(self) -> None:
        self.assertTrue((ROOT / "ACTUALIZAR-SISTEMA.cmd").is_file())
        self.assertEqual(list(ROOT.glob("MIGRAR-*.cmd")), [])

    def test_updater_never_drops_or_rebuilds_business_schema(self) -> None:
        sql = (ROOT / "db/bootstrap/apply_pending_migrations.sql").read_text(encoding="utf-8").upper()
        self.assertNotIn("DROP ", sql)
        self.assertNotIn("TRUNCATE ", sql)
        self.assertNotIn("DELETE FROM", sql)


if __name__ == "__main__":
    unittest.main()
