from pathlib import Path
import unittest


class ApprovedImageMaterializationMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = Path("db/migrations/0011_approved_image_materialization.sql").read_text(encoding="utf-8")

    def test_is_forward_only_append_only_and_one_primary_per_target(self) -> None:
        self.assertTrue(self.sql.lstrip().startswith("BEGIN;"))
        self.assertTrue(self.sql.rstrip().endswith("COMMIT;"))
        self.assertNotRegex(self.sql, r"(?i)DROP\s+|TRUNCATE\s+|DELETE\s+FROM")
        self.assertIn("GENERATED ALWAYS AS (COALESCE(product_variant_id, product_template_id))", self.sql)
        self.assertIn("UNIQUE (product_target_id)", self.sql)
        self.assertIn("trg_approved_image_materialization_append_only", self.sql)

    def test_storage_is_content_addressed_and_permissions_are_minimal(self) -> None:
        self.assertIn("^objects/[0-9a-f]{2}/[0-9a-f]{64}", self.sql)
        self.assertRegex(self.sql, r"(?is)GRANT SELECT, INSERT ON.*TO perfect_catalog_app")
        self.assertNotRegex(self.sql, r"(?is)GRANT (?:UPDATE|DELETE).*perfect_catalog_app")


if __name__ == "__main__":
    unittest.main()
