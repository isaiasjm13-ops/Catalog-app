"""Static contract tests for forward-only migration 0002."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


class PlanFutureTargetMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        path = (
            Path(__file__).resolve().parents[1]
            / "db"
            / "migrations"
            / "0002_plan_future_product_targets.sql"
        )
        cls.sql = path.read_text(encoding="utf-8")
        cls.compact = re.sub(r"\s+", " ", cls.sql)

    def test_migration_is_transactional_and_forward_only(self) -> None:
        self.assertRegex(self.sql.strip(), r"(?is)^BEGIN\s*;")
        self.assertRegex(self.sql.strip(), r"(?is)COMMIT\s*;\s*$")
        self.assertNotRegex(self.sql, r"(?i)DROP\s+TABLE|DROP\s+SCHEMA")
        self.assertNotIn("ON DELETE CASCADE", self.sql.upper())

    def test_existing_and_planned_targets_are_separate(self) -> None:
        for column in (
            "resolved_product_template_id",
            "resolved_product_variant_id",
            "planned_product_template_id",
            "planned_product_variant_id",
            "planned_product_target_id",
            "planned_product_scope",
        ):
            self.assertIn(column, self.sql)
        self.assertIn("planned_product_template_id uuid NOT NULL", self.sql)
        self.assertIn("fk_import_plan_item_resolved_template", self.sql)
        self.assertIn("fk_import_plan_item_resolved_variant", self.sql)

    def test_new_product_can_be_planned_without_existing_product_fk(self) -> None:
        self.assertIn("ck_import_plan_item_create_is_unresolved", self.sql)
        self.assertIn("operation_type <> 'create' OR resolved_product_template_id IS NULL", self.compact)
        self.assertNotRegex(
            self.sql,
            r"(?is)FOREIGN KEY\s*\(\s*planned_product_template_id\s*\)",
        )

    def test_existing_product_must_match_planned_identity(self) -> None:
        self.assertIn("ck_import_plan_item_resolved_matches_planned", self.sql)
        self.assertIn(
            "planned_product_template_id = resolved_product_template_id",
            self.compact,
        )
        self.assertIn(
            "planned_product_variant_id IS NOT DISTINCT FROM resolved_product_variant_id",
            self.compact,
        )

    def test_snapshot_matches_plan_and_real_product(self) -> None:
        self.assertIn("fk_inventory_snapshot_template", self.sql)
        self.assertIn("fk_inventory_snapshot_variant", self.sql)
        self.assertIn("fk_inventory_snapshot_exact_plan_item", self.sql)
        for column in (
            "planned_product_template_id",
            "planned_product_scope",
            "planned_product_target_id",
        ):
            self.assertIn(column, self.sql)

    def test_plan_file_row_context_is_preserved(self) -> None:
        context = (
            "import_plan_item_id, import_plan_id, import_file_id, "
            "staging_row_id, operation_type"
        )
        self.assertIn(context, self.compact)
        self.assertIn("uq_import_plan_item_snapshot_context", self.sql)


if __name__ == "__main__":
    unittest.main()
