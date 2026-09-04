from pathlib import Path
import unittest


class ImageVariantLetterSuffixMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = Path("db/migrations/0027_image_variant_letter_suffix.sql").read_text(encoding="utf-8")

    def test_is_forward_only_and_rerunnable(self) -> None:
        self.assertTrue(self.sql.lstrip().startswith("BEGIN;"))
        self.assertTrue(self.sql.rstrip().endswith("COMMIT;"))
        self.assertNotRegex(self.sql, r"(?i)DROP\s+TABLE|TRUNCATE\s+|DELETE\s+FROM")
        self.assertIn("DROP CONSTRAINT IF EXISTS ck_image_product_candidate_algorithm", self.sql)

    def test_widens_the_algorithm_check_without_dropping_historical_values(self) -> None:
        self.assertIn("exact-approved-reference-v1", self.sql)
        self.assertIn("exact-approved-reference-v2", self.sql)
        self.assertIn("exact-approved-reference-v3", self.sql)

    def test_records_its_own_ledger_entry(self) -> None:
        self.assertIn("INSERT INTO perfect_catalog.schema_migration", self.sql)
        self.assertIn("'0027_image_variant_letter_suffix', :'checksum_0027'", self.sql)


if __name__ == "__main__":
    unittest.main()
