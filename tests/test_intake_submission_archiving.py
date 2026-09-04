from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "db" / "migrations" / "0024_intake_submission_archiving.sql"


class IntakeSubmissionArchivingMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")

    def test_migration_is_transactional_and_forward_only(self) -> None:
        self.assertTrue(self.sql.lstrip().startswith("BEGIN;"))
        self.assertTrue(self.sql.rstrip().endswith("COMMIT;"))
        self.assertNotIn("DROP TABLE", self.sql.upper())
        self.assertNotIn("ALTER TABLE perfect_catalog.intake_submission ", self.sql)

    def test_event_table_is_append_only_with_minimal_permissions(self) -> None:
        self.assertIn("trg_intake_submission_archive_event_append_only", self.sql)
        self.assertIn("guard_append_only_row", self.sql)
        self.assertIn("GRANT SELECT, INSERT ON perfect_catalog.intake_submission_archive_event", self.sql)
        self.assertNotIn("GRANT UPDATE ON perfect_catalog.intake_submission_archive_event", self.sql)
        self.assertNotIn("GRANT DELETE", self.sql.upper())

    def test_does_not_grant_update_on_the_original_append_only_table(self) -> None:
        # intake_submission (0007) must stay fully append-only; archiving is a
        # derived state from a separate event table, never a column on it.
        self.assertNotIn("GRANT UPDATE", self.sql.upper().split("INTAKE_SUBMISSION_ARCHIVE_EVENT")[0])

    def test_bootstrap_validates_the_append_only_guard_survives(self) -> None:
        bootstrap = (ROOT / "db/bootstrap/apply_pending_migrations.sql").read_text(encoding="utf-8")
        self.assertIn("\\ir ../migrations/0024_intake_submission_archiving.sql", bootstrap)
        self.assertIn(
            "has_table_privilege('perfect_catalog_app', 'perfect_catalog.intake_submission', 'UPDATE')",
            bootstrap,
        )
        self.assertIn("trg_intake_submission_archive_event_append_only", bootstrap)


class IntakeSubmissionArchivingLogicTests(unittest.TestCase):
    def test_archive_intake_submission_validates_actor_and_reason_before_the_database(self) -> None:
        from perfect_catalog.intake import archive_intake_submission

        with self.assertRaisesRegex(ValueError, "actor"):
            archive_intake_submission(
                config=None, password=None, submission_id="00000000-0000-0000-0000-000000000001",
                archived=True, actor="", reason="Motivo suficientemente largo",
            )
        with self.assertRaisesRegex(ValueError, "motivo|reason"):
            archive_intake_submission(
                config=None, password=None, submission_id="00000000-0000-0000-0000-000000000001",
                archived=True, actor="reviewer", reason="no",
            )

    def test_listing_supports_the_archived_filter_values(self) -> None:
        from perfect_catalog.intake import INTAKE_ARCHIVE_FILTERS

        self.assertEqual(INTAKE_ARCHIVE_FILTERS, {"active", "archived", "all"})


if __name__ == "__main__":
    unittest.main()
