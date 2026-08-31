from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CompanyMigrationTests(unittest.TestCase):
    def test_ledger_is_owner_controlled_and_checksum_bound(self) -> None:
        sql = (ROOT / "db/migrations/0017_migration_ledger.sql").read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE perfect_catalog.schema_migration", sql)
        self.assertIn("checksum_sha256 char(64) NOT NULL", sql)
        self.assertIn("VALUES (\n    '0017_migration_ledger', :'checksum_0017'", sql)
        self.assertIn("REVOKE ALL ON perfect_catalog.schema_migration FROM PUBLIC", sql)
        self.assertNotIn("perfect_catalog_app;", sql)

    def test_company_backfill_is_explicit_complete_and_non_destructive(self) -> None:
        sql = (ROOT / "db/migrations/0018_companies.sql").read_text(encoding="utf-8")
        for code in ("PERFECT", "KMC", "NATSUKI", "MASAKI", "PDM"):
            self.assertIn(f"'{code}'", sql)
        self.assertIn("WHEN 'EXACTCARS' THEN", sql)
        self.assertIn("WHEN 'NATSUKI' THEN", sql)
        self.assertIn("Hay marcas sin mapping Company", sql)
        self.assertIn("ALTER COLUMN company_id SET NOT NULL", sql)
        self.assertIn("ON DELETE RESTRICT", sql)
        self.assertNotIn("DELETE FROM", sql.upper())
        self.assertNotIn("DROP ", sql.upper())

    def test_updater_calculates_checksums_instead_of_hardcoding_them(self) -> None:
        script = (ROOT / "db/bootstrap/run_pending_migrations.ps1").read_text(encoding="utf-8")
        self.assertIn("Get-FileHash -LiteralPath $migration0017 -Algorithm SHA256", script)
        self.assertIn("Get-FileHash -LiteralPath $migration0018 -Algorithm SHA256", script)
        self.assertIn('"checksum_0017=$checksum0017"', script)
        self.assertIn('"checksum_0018=$checksum0018"', script)

    def test_updater_enforces_post_migration_company_invariants(self) -> None:
        sql = (ROOT / "db/bootstrap/apply_pending_migrations.sql").read_text(encoding="utf-8")
        self.assertIn("faltan entradas 0017-0018 en el ledger", sql)
        self.assertIn("SELECT 1 FROM perfect_catalog.brand WHERE company_id IS NULL", sql)
        self.assertIn("b.code = 'EXACTCARS' AND c.code <> 'PERFECT'", sql)
        self.assertIn("b.code = 'NATSUKI' AND c.code <> 'NATSUKI'", sql)
        self.assertIn("Base de datos actualizada y validada", sql)


if __name__ == "__main__":
    unittest.main()
