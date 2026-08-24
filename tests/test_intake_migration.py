from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "db" / "migrations" / "0007_secure_intake.sql"
BOOTSTRAP = ROOT / "db" / "bootstrap" / "apply_intake_migration.sql"


class IntakeMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")
        cls.upper = cls.sql.upper()

    def test_migration_is_transactional_and_forward_only(self) -> None:
        self.assertTrue(self.sql.lstrip().startswith("BEGIN;"))
        self.assertTrue(self.sql.rstrip().endswith("COMMIT;"))
        self.assertNotRegex(self.upper, r"\bDROP\s+(?:TABLE|SCHEMA|DATABASE)\b")
        self.assertNotRegex(self.upper, r"\bDELETE\s+FROM\b|\bTRUNCATE\s+")

    def test_tables_capture_immutable_bytes_and_submission_evidence(self) -> None:
        self.assertEqual(
            set(re.findall(r"CREATE TABLE perfect_catalog\.([a-z_]+)", self.sql)),
            {"intake_asset", "intake_submission"},
        )
        self.assertIn("uq_intake_asset_sha256 UNIQUE (sha256)", self.sql)
        self.assertIn("validation_status IN ('quarantined', 'rejected')", self.sql)
        self.assertIn("jsonb_typeof(validation_report) = 'object'", self.sql)
        self.assertIn("validation_status = 'quarantined' AND intake_asset_id IS NOT NULL", self.sql)
        self.assertNotRegex(self.sql, r"(?i)ON DELETE CASCADE")

    def test_rows_are_append_only_and_application_permissions_are_minimal(self) -> None:
        self.assertEqual(
            set(re.findall(r"CREATE TRIGGER\s+([a-z_]+)", self.sql, re.I)),
            {"trg_intake_asset_append_only", "trg_intake_submission_append_only"},
        )
        self.assertEqual(self.sql.count("guard_append_only_row()"), 2)
        self.assertRegex(
            self.sql,
            r"(?is)GRANT SELECT, INSERT\s+ON perfect_catalog\.intake_asset, "
            r"perfect_catalog\.intake_submission\s+TO perfect_catalog_app",
        )
        self.assertNotRegex(self.sql, r"(?i)GRANT\s+(?:UPDATE|DELETE)")

    def test_bootstrap_uses_owner_and_restores_role(self) -> None:
        bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
        self.assertIn("SET ROLE perfect_catalog_owner;", bootstrap)
        self.assertIn("\\ir ../migrations/0007_secure_intake.sql", bootstrap)
        self.assertTrue(bootstrap.rstrip().endswith("RESET ROLE;"))


if __name__ == "__main__":
    unittest.main()
