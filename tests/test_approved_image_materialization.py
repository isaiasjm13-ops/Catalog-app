from __future__ import annotations

import hashlib
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

from perfect_catalog.approved_image_materialization import materialize_approved_image
from perfect_catalog.config import DatabaseConfig


class MaterializeApprovedImageVariantRoutingTests(unittest.TestCase):
    """A candidate without `variant_index` is the product's main photo (one per product,
    `approved_image_materialization`); a candidate with `variant_index` is an extra gallery
    photo (`approved_image_variant`, several per product). `materialize_approved_image` must
    route to the right table on its own — every caller (individual, bulk, modo simple) calls
    the same function without knowing which table applies."""

    def _connection_mock(self, record: dict, existing) -> tuple[Mock, Mock]:
        cursor = Mock()
        cursor.fetchone.side_effect = [record, existing]
        cursor_context = Mock()
        cursor_context.__enter__ = Mock(return_value=cursor)
        cursor_context.__exit__ = Mock(return_value=False)
        connection = Mock()
        connection.cursor.return_value = cursor_context
        connection_context = Mock()
        connection_context.__enter__ = Mock(return_value=connection)
        connection_context.__exit__ = Mock(return_value=False)
        return connection, connection_context

    def _base_record(self, root: Path, **overrides) -> dict:
        archive_path = root / "intake" / "archive.zip"
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        archive_path.write_bytes(b"quarantined-zip-bytes")
        record = {
            "image_product_decision_id": uuid.uuid4(), "decision": "approved",
            "candidate_evidence_sha256": "a" * 64, "image_product_candidate_id": uuid.uuid4(),
            "evidence_sha256": "a" * 64, "variant_index": None,
            "product_template_id": uuid.uuid4(), "product_variant_id": None,
            "image_archive_entry_id": uuid.uuid4(), "member_path": "photo.jpg",
            "original_filename": "REF-1234.jpg", "extension": ".jpg", "media_type": "image/jpeg",
            "uncompressed_size": 12345, "crc32": "deadbeef",
            "content_sha256": hashlib.sha256(b"approved-photo-bytes").hexdigest(),
            "archive_relpath": "archive.zip", "archive_size": archive_path.stat().st_size,
            "archive_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        }
        record.update(overrides)
        return record

    def _materialize(self, root: Path, record: dict, existing=None):
        connection, connection_context = self._connection_mock(record, existing)
        with (
            patch("perfect_catalog.approved_image_materialization.psycopg.connect", return_value=connection_context),
            patch("perfect_catalog.approved_image_materialization._copy_verified_member"),
        ):
            result = materialize_approved_image(
                record["image_product_candidate_id"], record["evidence_sha256"],
                root / "intake", root / "images", DatabaseConfig(), "secret",
                actor="isa", reason="Copia verificada", company_id=uuid.uuid4(),
            )
        return result, connection

    def test_primary_candidate_inserts_into_the_materialization_table(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            record = self._base_record(root, variant_index=None)
            result, connection = self._materialize(root, record)
        self.assertEqual(result["status"], "materialized")
        self.assertIn("approved_image_materialization_id", result)
        self.assertNotIn("variant_index", result)
        insert_sql = connection.execute.call_args_list[-1].args[0]
        self.assertIn("INSERT INTO perfect_catalog.approved_image_materialization", insert_sql)

    def test_variant_candidate_inserts_into_the_variant_table_with_its_index(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            record = self._base_record(root, variant_index=3)
            result, connection = self._materialize(root, record)
        self.assertEqual(result["status"], "materialized")
        self.assertEqual(result["variant_index"], 3)
        self.assertIn("approved_image_variant_id", result)
        insert_sql = connection.execute.call_args_list[-1].args[0]
        insert_args = connection.execute.call_args_list[-1].args[1]
        self.assertIn("INSERT INTO perfect_catalog.approved_image_variant", insert_sql)
        self.assertIn(3, insert_args)

    def test_already_materialized_primary_checks_the_primary_table_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            record = self._base_record(root, variant_index=None)
            existing = {
                "approved_image_materialization_id": uuid.uuid4(),
                "storage_relpath": "objects/aa/aaaa.jpg", "content_sha256": "a" * 64,
            }
            result, connection = self._materialize(root, record, existing=existing)
        self.assertEqual(result["status"], "already_materialized")
        select_sql = connection.cursor.return_value.__enter__.return_value.execute.call_args_list[-1].args[0]
        self.assertIn("FROM perfect_catalog.approved_image_materialization", select_sql)

    def test_already_materialized_variant_checks_the_variant_table_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            record = self._base_record(root, variant_index=2)
            existing = {
                "approved_image_variant_id": uuid.uuid4(),
                "storage_relpath": "objects/bb/bbbb.jpg", "content_sha256": "b" * 64,
            }
            result, connection = self._materialize(root, record, existing=existing)
        self.assertEqual(result["status"], "already_materialized")
        select_sql = connection.cursor.return_value.__enter__.return_value.execute.call_args_list[-1].args[0]
        self.assertIn("FROM perfect_catalog.approved_image_variant", select_sql)


if __name__ == "__main__":
    unittest.main()
