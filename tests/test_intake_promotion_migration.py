import re
import unittest
from pathlib import Path


class IntakePromotionMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = Path("db/migrations/0008_intake_promotion.sql").read_text(encoding="utf-8")

    def test_migration_is_forward_only_and_transactional(self) -> None:
        self.assertTrue(self.sql.lstrip().startswith("BEGIN;"))
        self.assertTrue(self.sql.rstrip().endswith("COMMIT;"))
        self.assertNotRegex(self.sql, r"(?i)DROP\s+|TRUNCATE\s+|DELETE\s+FROM")

    def test_evidence_is_append_only_and_contextually_linked(self) -> None:
        for token in (
            "CREATE TABLE IF NOT EXISTS perfect_catalog.intake_promotion",
            "uq_intake_promotion_submission",
            "fk_intake_promotion_submission_asset",
            "fk_intake_promotion_asset_sha",
            "fk_intake_promotion_plan_batch",
            "trg_intake_promotion_append_only",
        ):
            self.assertIn(token, self.sql)
        self.assertRegex(self.sql, r"(?is)BEFORE UPDATE OR DELETE.*guard_append_only_row")

    def test_prerequisite_constraints_are_safely_resumable(self) -> None:
        self.assertIn("FROM pg_constraint", self.sql)
        self.assertIn("'perfect_catalog.intake_submission'::regclass", self.sql)
        self.assertIn("'perfect_catalog.intake_asset'::regclass", self.sql)
        self.assertIn("'perfect_catalog.import_plan'::regclass", self.sql)
        self.assertIn("CREATE INDEX IF NOT EXISTS ix_intake_promotion_promoted", self.sql)
        self.assertIn("FROM pg_trigger", self.sql)
        self.assertIn("La tabla intake_promotion está incompleta", self.sql)

    def test_application_permissions_are_minimal(self) -> None:
        self.assertRegex(self.sql, r"(?is)GRANT SELECT, INSERT ON perfect_catalog\.intake_promotion TO perfect_catalog_app")
        self.assertNotRegex(self.sql, r"(?is)GRANT (?:UPDATE|DELETE).*intake_promotion")
