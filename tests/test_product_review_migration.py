from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "db" / "migrations" / "0006_product_review_workflow.sql"
RESET = ROOT / "db" / "bootstrap" / "reset_imported_data.sql"


class ProductReviewMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")
        cls.upper = cls.sql.upper()

    def test_migration_is_transactional_and_forward_only(self) -> None:
        self.assertTrue(self.sql.lstrip().startswith("BEGIN;"))
        self.assertTrue(self.sql.rstrip().endswith("COMMIT;"))
        self.assertNotRegex(self.upper, r"\bDROP\s+(?:TABLE|SCHEMA|DATABASE)\b")
        self.assertNotRegex(self.upper, r"\bDELETE\s+FROM\b|\bTRUNCATE\s+")

    def test_pending_review_transitions_are_guarded(self) -> None:
        self.assertEqual(
            set(
                re.findall(
                    r"CREATE (?:CONSTRAINT )?TRIGGER\s+([a-z_]+)",
                    self.sql,
                    re.I,
                )
            ),
            {
                "trg_product_template_review",
                "trg_product_variant_review",
                "trg_product_reference_review",
                "trg_product_template_review_alignment",
                "trg_product_variant_review_alignment",
                "trg_product_reference_review_alignment",
            },
        )
        self.assertIn("OLD.catalog_status <> 'pending_review'", self.sql)
        self.assertIn("NEW.catalog_status NOT IN ('active', 'inactive')", self.sql)
        self.assertIn("NEW.review_status NOT IN ('approved', 'rejected')", self.sql)
        self.assertEqual(self.upper.count("DEFERRABLE INITIALLY DEFERRED"), 3)
        self.assertIn("review requires one aligned primary reference", self.sql)
        self.assertIn("review is not aligned with its identity", self.sql)

    def test_application_updates_are_column_scoped(self) -> None:
        self.assertRegex(
            self.sql,
            r"(?is)GRANT UPDATE \(catalog_status, updated_at\)\s+ON "
            r"perfect_catalog\.product_template, perfect_catalog\.product_variant",
        )
        self.assertRegex(
            self.sql,
            r"(?is)GRANT UPDATE \(review_status, reviewed_by, reviewed_at, "
            r"review_note, updated_at\)\s+ON perfect_catalog\.product_reference",
        )
        self.assertNotRegex(self.sql, r"(?i)GRANT\s+UPDATE\s+ON")
        self.assertNotRegex(self.sql, r"(?i)GRANT\s+DELETE")

    def test_central_rebuild_uses_owner_and_applies_migration(self) -> None:
        reset = RESET.read_text(encoding="utf-8")
        self.assertIn("SET ROLE perfect_catalog_owner;", reset)
        self.assertIn("\\ir ../migrations/0006_product_review_workflow.sql", reset)
        self.assertIn("RESET ROLE;", reset)


if __name__ == "__main__":
    unittest.main()
