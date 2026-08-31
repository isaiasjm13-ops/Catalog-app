from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "db" / "migrations" / "0004_restore_application_reads.sql"
RESET = ROOT / "db" / "bootstrap" / "reset_imported_data.sql"


class ApplicationReadsMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")
        cls.upper = cls.sql.upper()

    def test_migration_is_transactional_and_non_destructive(self) -> None:
        self.assertTrue(self.sql.lstrip().startswith("BEGIN;"))
        self.assertTrue(self.sql.rstrip().endswith("COMMIT;"))
        self.assertNotRegex(
            self.upper,
            r"\b(?:DROP|DELETE|TRUNCATE|UPDATE|INSERT|ALTER\s+TABLE)\b",
        )

    def test_only_current_application_dependencies_are_readable(self) -> None:
        expected_tables = {
            "source_system",
            "import_batch",
            "import_file",
            "staging_row",
            "staging_row_result",
            "import_issue",
            "import_plan",
            "import_plan_item",
            "brand",
            "product_category",
            "product_template",
            "product_variant",
            "product_reference",
            "inventory_snapshot",
            "media_asset",
            "product_media",
            "catalog_release",
            "catalog_release_item",
        }
        granted_tables = set(re.findall(r"perfect_catalog\.([a-z_]+)", self.sql))
        self.assertEqual(granted_tables, expected_tables)
        self.assertIn("TO perfect_catalog_app;", self.sql)
        self.assertNotIn("ALL TABLES", self.upper)
        self.assertNotIn("perfect_catalog_readonly", self.sql)
        self.assertNotRegex(self.sql, r"(?i)GRANT\s+(?:INSERT|UPDATE|DELETE)")

    def test_central_rebuild_uses_owner_and_applies_migration(self) -> None:
        reset = RESET.read_text(encoding="utf-8")
        self.assertIn("SET ROLE perfect_catalog_owner;", reset)
        self.assertIn("\\ir ../migrations/0004_restore_application_reads.sql", reset)
        self.assertIn("RESET ROLE;", reset)


if __name__ == "__main__":
    unittest.main()
