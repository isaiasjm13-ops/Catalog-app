from pathlib import Path
import unittest


class ProductPhotoVariantsMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = Path("db/migrations/0026_product_photo_variants.sql").read_text(encoding="utf-8")

    def test_is_forward_only_and_leaves_the_primary_photo_pipeline_untouched(self) -> None:
        self.assertTrue(self.sql.lstrip().startswith("BEGIN;"))
        self.assertTrue(self.sql.rstrip().endswith("COMMIT;"))
        self.assertNotRegex(self.sql, r"(?i)DROP\s+TABLE|TRUNCATE\s+|DELETE\s+FROM")
        self.assertNotIn("approved_image_materialization_id", self.sql)

    def test_new_table_allows_many_variants_per_product_ordered_by_index(self) -> None:
        self.assertIn("GENERATED ALWAYS AS (COALESCE(product_variant_id, product_template_id))", self.sql)
        self.assertIn("UNIQUE (product_target_id, variant_index)", self.sql)
        self.assertNotIn("UNIQUE (product_target_id)\n", self.sql)
        self.assertIn("CHECK (variant_index >= 2)", self.sql)
        self.assertIn("trg_approved_image_variant_append_only", self.sql)

    def test_candidate_table_gains_an_optional_variant_index(self) -> None:
        self.assertIn("ADD COLUMN IF NOT EXISTS variant_index integer NULL", self.sql)
        self.assertIn("CHECK (variant_index IS NULL OR variant_index >= 2)", self.sql)
        self.assertIn("exact-approved-reference-v1", self.sql)
        self.assertIn("exact-approved-reference-v2", self.sql)

    def test_storage_is_content_addressed_and_permissions_are_minimal(self) -> None:
        self.assertIn("^objects/[0-9a-f]{2}/[0-9a-f]{64}", self.sql)
        self.assertIn("GRANT SELECT, INSERT ON perfect_catalog.approved_image_variant TO perfect_catalog_app", self.sql)
        self.assertNotRegex(self.sql, r"(?is)GRANT (?:UPDATE|DELETE).*perfect_catalog_app")

    def test_every_ddl_statement_can_safely_rerun_after_a_partial_apply(self) -> None:
        """Si el updater corre este archivo con el esquema ya aplicado pero sin fila en el
        ledger (por ejemplo, porque un intento anterior falló después de aplicar el DDL), cada
        sentencia debe poder repetirse sin error: de ahí viene el bug real que motivó este test
        (faltaba justamente el INSERT al ledger, y el archivo no era re-ejecutable)."""
        self.assertIn("CREATE TABLE IF NOT EXISTS perfect_catalog.approved_image_variant", self.sql)
        self.assertIn("CREATE INDEX IF NOT EXISTS ix_approved_image_variant_product", self.sql)
        self.assertIn("CREATE INDEX IF NOT EXISTS ix_approved_image_variant_target", self.sql)
        self.assertIn("DROP CONSTRAINT IF EXISTS ck_image_product_candidate_algorithm", self.sql)
        self.assertRegex(
            self.sql,
            r"(?s)IF NOT EXISTS \(SELECT 1 FROM pg_constraint WHERE conname='ck_image_product_candidate_variant_index'",
        )
        self.assertRegex(
            self.sql,
            r"(?s)IF NOT EXISTS \(SELECT 1 FROM pg_trigger WHERE tgname='trg_approved_image_variant_append_only'",
        )

    def test_records_its_own_ledger_entry(self) -> None:
        """El bug real: esta migración aplicaba todo el DDL pero nunca insertaba su propia fila
        en schema_migration, así que el validador del ledger siempre fallaba después."""
        self.assertIn("INSERT INTO perfect_catalog.schema_migration", self.sql)
        self.assertIn("'0026_product_photo_variants', :'checksum_0026'", self.sql)


if __name__ == "__main__":
    unittest.main()
