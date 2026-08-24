from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "db" / "migrations" / "0003_apply_workflow_permissions.sql"
BOOTSTRAP = ROOT / "db" / "bootstrap" / "apply_apply_workflow_migration.sql"


class ApplyWorkflowMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")
        cls.upper = cls.sql.upper()

    def test_migration_is_transactional_and_forward_only(self) -> None:
        self.assertTrue(self.sql.lstrip().startswith("BEGIN;"))
        self.assertTrue(self.sql.rstrip().endswith("COMMIT;"))
        self.assertNotRegex(self.upper, r"\bDROP\s+(?:TABLE|SCHEMA|DATABASE)\b")
        self.assertNotRegex(self.upper, r"\bDELETE\s+FROM\b")

    def test_missing_variant_count_stays_unknown(self) -> None:
        self.assertIn("ALTER COLUMN variant_count_observed DROP NOT NULL", self.sql)
        self.assertNotIn("DEFAULT 0", self.upper)

    def test_application_role_has_column_scoped_state_transitions(self) -> None:
        self.assertIn(
            "REVOKE UPDATE ON perfect_catalog.source_system FROM perfect_catalog_app;",
            self.sql,
        )
        self.assertIn(
            "REVOKE UPDATE ON perfect_catalog.import_batch FROM perfect_catalog_app;",
            self.sql,
        )
        self.assertRegex(
            self.sql,
            r"(?is)GRANT UPDATE \(name, system_type, updated_at\).*?source_system",
        )
        self.assertRegex(
            self.sql,
            r"(?is)GRANT UPDATE \(status, approved_by, finished_at, statistics\).*?import_batch",
        )
        self.assertRegex(
            self.sql,
            r"(?is)GRANT UPDATE \(plan_status, approved_at, approved_by, applied_at, applied_by\).*?import_plan",
        )
        self.assertNotRegex(self.sql, r"(?i)GRANT\s+UPDATE\s+ON")
        self.assertNotRegex(self.sql, r"(?i)GRANT\s+DELETE")

    def test_only_required_business_inserts_are_granted(self) -> None:
        for table in (
            "brand",
            "product_category",
            "product_template",
            "product_reference",
            "inventory_snapshot",
            "audit_event",
        ):
            self.assertRegex(self.sql, rf"(?i)perfect_catalog\.{table}\b")

    def test_bootstrap_restores_owner_role(self) -> None:
        bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
        self.assertIn("SET ROLE perfect_catalog_owner;", bootstrap)
        self.assertIn("\\ir ../migrations/0003_apply_workflow_permissions.sql", bootstrap)
        self.assertTrue(bootstrap.rstrip().endswith("RESET ROLE;"))


if __name__ == "__main__":
    unittest.main()
