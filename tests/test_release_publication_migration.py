from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "db" / "migrations" / "0005_release_publication_workflow.sql"
BOOTSTRAP = ROOT / "db" / "bootstrap" / "apply_release_publication_migration.sql"


class ReleasePublicationMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")
        cls.upper = cls.sql.upper()

    def test_migration_is_transactional_and_forward_only(self) -> None:
        self.assertTrue(self.sql.lstrip().startswith("BEGIN;"))
        self.assertTrue(self.sql.rstrip().endswith("COMMIT;"))
        self.assertNotRegex(self.upper, r"\bDROP\s+(?:TABLE|SCHEMA|DATABASE)\b")
        self.assertNotRegex(self.upper, r"\bDELETE\s+FROM\b|\bTRUNCATE\s+")

    def test_release_and_audit_rows_are_protected_by_triggers(self) -> None:
        expected = {
            "trg_catalog_release_insert",
            "trg_catalog_release_update",
            "trg_catalog_release_delete",
            "trg_catalog_release_item_insert",
            "trg_catalog_release_item_append_only",
            "trg_audit_event_append_only",
        }
        triggers = set(re.findall(r"CREATE TRIGGER\s+([a-z_]+)", self.sql, re.I))
        self.assertEqual(triggers, expected)
        self.assertIn("FOR SHARE", self.upper)
        self.assertIn("OLD.status = 'draft' AND NEW.status = 'published'", self.sql)
        self.assertIn("OLD.status = 'published' AND NEW.status = 'archived'", self.sql)

    def test_public_identity_is_unique_inside_release(self) -> None:
        self.assertRegex(
            self.sql,
            r"(?is)CREATE UNIQUE INDEX uq_catalog_release_item_public_identity.*?"
            r"COALESCE\(product_variant_id, product_template_id\)",
        )

    def test_application_permissions_are_minimal(self) -> None:
        self.assertRegex(
            self.sql,
            r"(?is)GRANT INSERT\s+ON perfect_catalog\.catalog_release,\s*"
            r"perfect_catalog\.catalog_release_item\s+TO perfect_catalog_app",
        )
        self.assertRegex(
            self.sql,
            r"(?is)GRANT UPDATE \(status, published_at, published_by, archived_at, archived_by\)"
            r"\s+ON perfect_catalog\.catalog_release",
        )
        self.assertNotRegex(self.sql, r"(?i)GRANT\s+DELETE")
        self.assertNotRegex(self.sql, r"(?i)GRANT\s+UPDATE\s+ON")

    def test_bootstrap_uses_owner_and_restores_role(self) -> None:
        bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
        self.assertIn("SET ROLE perfect_catalog_owner;", bootstrap)
        self.assertIn("\\ir ../migrations/0005_release_publication_workflow.sql", bootstrap)
        self.assertTrue(bootstrap.rstrip().endswith("RESET ROLE;"))


if __name__ == "__main__":
    unittest.main()
