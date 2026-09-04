from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "db/migrations/0022_controlled_product_updates.sql"


class ControlledProductUpdateMigrationTests(unittest.TestCase):
    def test_migration_keeps_direct_update_blocked_and_uses_definer_function(self) -> None:
        sql = MIGRATION.read_text(encoding="utf-8")
        upper = sql.upper()
        self.assertIn("SECURITY DEFINER", upper)
        self.assertIn("SET SEARCH_PATH = PG_CATALOG, PERFECT_CATALOG", upper)
        self.assertIn("REVOKE ALL ON FUNCTION", upper)
        self.assertIn("FROM PUBLIC", upper)
        self.assertIn("REVOKE UPDATE ON PERFECT_CATALOG.PRODUCT_TEMPLATE FROM PERFECT_CATALOG_APP", upper)
        self.assertIn("GRANT UPDATE (CATALOG_STATUS, UPDATED_AT)", upper)
        self.assertNotIn("DISABLE TRIGGER", upper)
        self.assertNotIn("DROP TRIGGER", upper)

    def test_controlled_path_requires_approved_applying_plan_and_before_values(self) -> None:
        sql = MIGRATION.read_text(encoding="utf-8")
        self.assertIn("v_plan.plan_status <> 'applying'", sql)
        self.assertIn("v_plan.approved_at IS NULL", sql)
        self.assertIn("controlled update fingerprint mismatch", sql)
        self.assertIn("controlled update before_values are incomplete", sql)
        self.assertIn("product changed after plan approval", sql)
        self.assertIn("Company/Brand/source context changed after approval", sql)

    def test_only_trusted_owner_plus_transaction_local_marker_can_bypass_review_guard(self) -> None:
        sql = MIGRATION.read_text(encoding="utf-8")
        self.assertIn("current_user = 'perfect_catalog_owner'", sql)
        self.assertIn("perfect_catalog.controlled_product_update", sql)
        self.assertIn("set_config('perfect_catalog.controlled_product_update', 'on', true)", sql)
        self.assertIn("controlled product update attempted to change protected identity/local fields", sql)

    def test_review_alignment_is_preserved_for_status_transitions(self) -> None:
        sql = MIGRATION.read_text(encoding="utf-8")
        self.assertIn("OLD.catalog_status IS NOT DISTINCT FROM NEW.catalog_status", sql)
        self.assertIn("product_template review requires one aligned primary reference", sql)


if __name__ == "__main__":
    unittest.main()
