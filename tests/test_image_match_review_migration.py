from pathlib import Path
import unittest


class ImageMatchReviewMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = Path("db/migrations/0010_image_match_review.sql").read_text(encoding="utf-8")

    def test_is_transactional_forward_only_and_append_only(self) -> None:
        self.assertTrue(self.sql.lstrip().startswith("BEGIN;"))
        self.assertTrue(self.sql.rstrip().endswith("COMMIT;"))
        self.assertNotRegex(self.sql, r"(?i)DROP\s+|TRUNCATE\s+|DELETE\s+FROM")
        self.assertIn("trg_image_product_candidate_append_only", self.sql)
        self.assertIn("trg_image_product_decision_append_only", self.sql)

    def test_candidates_are_separate_from_human_decisions(self) -> None:
        self.assertIn("CREATE TABLE perfect_catalog.image_product_candidate", self.sql)
        self.assertIn("CREATE TABLE perfect_catalog.image_product_decision", self.sql)
        self.assertIn("exact-approved-reference-v1", self.sql)
        self.assertIn("UNIQUE (image_product_candidate_id)", self.sql)
        self.assertIn("decision IN ('approved', 'rejected')", self.sql)

    def test_application_permissions_are_minimal(self) -> None:
        self.assertRegex(self.sql, r"(?is)GRANT SELECT, INSERT ON.*TO perfect_catalog_app")
        self.assertNotRegex(self.sql, r"(?is)GRANT (?:UPDATE|DELETE).*perfect_catalog_app")
        bootstrap = Path("db/bootstrap/apply_image_match_review_migration.sql").read_text(encoding="utf-8")
        self.assertIn("\\ir ../migrations/0010_image_match_review.sql", bootstrap)


if __name__ == "__main__":
    unittest.main()
