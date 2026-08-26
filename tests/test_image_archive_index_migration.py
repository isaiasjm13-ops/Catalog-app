import unittest
from pathlib import Path


class ImageArchiveIndexMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = Path("db/migrations/0009_image_archive_index.sql").read_text(encoding="utf-8")

    def test_migration_is_transactional_forward_only(self) -> None:
        self.assertTrue(self.sql.lstrip().startswith("BEGIN;"))
        self.assertTrue(self.sql.rstrip().endswith("COMMIT;"))
        for forbidden in ("DROP ", "TRUNCATE ", "DELETE FROM"):
            self.assertNotIn(forbidden, self.sql.upper())

    def test_index_and_entries_are_append_only_with_exact_source_context(self) -> None:
        for token in (
            "CREATE TABLE perfect_catalog.image_archive_index",
            "CREATE TABLE perfect_catalog.image_archive_entry",
            "fk_image_archive_index_submission_asset",
            "fk_image_archive_index_asset_sha",
            "trg_image_archive_index_append_only",
            "trg_image_archive_entry_append_only",
        ):
            self.assertIn(token, self.sql)

    def test_no_product_or_media_association_is_created(self) -> None:
        self.assertNotIn("product_media", self.sql)
        self.assertNotIn("media_asset", self.sql)
        self.assertIn("match_status IN ('unmatched', 'ambiguous')", self.sql)

    def test_application_permissions_are_select_insert_only(self) -> None:
        self.assertIn("GRANT SELECT, INSERT ON perfect_catalog.image_archive_index", self.sql)
        self.assertNotIn("GRANT UPDATE", self.sql)
        self.assertNotIn("GRANT DELETE", self.sql)

