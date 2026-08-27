import unittest
import uuid
from unittest.mock import Mock, patch

from perfect_catalog.config import DatabaseConfig
from perfect_catalog.image_match_review import (
    MATCH_ALGORITHM, decide_image_candidates_bulk, exact_image_candidates,
)


class ImageMatchReviewTests(unittest.TestCase):
    def test_only_exact_normalized_approved_reference_inputs_become_candidates(self) -> None:
        entry_id, reference_id, product_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        entries = [{"image_archive_entry_id": entry_id, "content_sha256": "a" * 64, "lookup_key": "NK-001"}]
        references = [{
            "product_reference_id": reference_id, "product_template_id": product_id,
            "product_variant_id": None, "value_original": "NK 001", "value_normalized": "NK-001",
        }, {
            "product_reference_id": uuid.uuid4(), "product_template_id": uuid.uuid4(),
            "product_variant_id": None, "value_original": "NK-002", "value_normalized": "NK-002",
        }]
        candidates = exact_image_candidates(entries, references)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["algorithm"], MATCH_ALGORITHM)
        self.assertEqual(candidates[0]["product_reference_id"], str(reference_id))
        self.assertEqual(len(candidates[0]["evidence_sha256"]), 64)

    def test_candidate_identity_and_evidence_are_deterministic(self) -> None:
        entry_id, reference_id, product_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        entries = [{"image_archive_entry_id": entry_id, "content_sha256": "b" * 64, "lookup_key": "ABC-1"}]
        references = [{"product_reference_id": reference_id, "product_template_id": product_id,
                       "product_variant_id": None, "value_original": "ABC-1", "value_normalized": "ABC-1"}]
        self.assertEqual(exact_image_candidates(entries, references), exact_image_candidates(entries, references))

    def test_bulk_decision_locks_exact_pending_set_and_preserves_each_hash(self) -> None:
        candidates = [
            {"image_product_candidate_id": uuid.uuid4(), "evidence_sha256": "a" * 64},
            {"image_product_candidate_id": uuid.uuid4(), "evidence_sha256": "b" * 64},
        ]
        cursor = Mock(); cursor.fetchall.return_value = candidates
        cursor_context = Mock(); cursor_context.__enter__ = Mock(return_value=cursor); cursor_context.__exit__ = Mock(return_value=False)
        connection = Mock(); connection.cursor.return_value = cursor_context
        connection_context = Mock(); connection_context.__enter__ = Mock(return_value=connection); connection_context.__exit__ = Mock(return_value=False)
        with patch("perfect_catalog.image_match_review.psycopg.connect", return_value=connection_context):
            result = decide_image_candidates_bulk(
                2, "approved", "isa", "Lote exacto revisado", DatabaseConfig(), "secret"
            )
        self.assertEqual(result, {"status": "bulk_approved", "count": 2})
        insert_calls = [call for call in cursor.execute.call_args_list if "INSERT INTO" in call.args[0]]
        self.assertEqual(len(insert_calls), 2)
        self.assertEqual([call.args[1][3] for call in insert_calls], ["a" * 64, "b" * 64])

    def test_bulk_decision_rejects_if_pending_count_changed(self) -> None:
        cursor = Mock(); cursor.fetchall.return_value = []
        cursor_context = Mock(); cursor_context.__enter__ = Mock(return_value=cursor); cursor_context.__exit__ = Mock(return_value=False)
        connection = Mock(); connection.cursor.return_value = cursor_context
        connection_context = Mock(); connection_context.__enter__ = Mock(return_value=connection); connection_context.__exit__ = Mock(return_value=False)
        with patch("perfect_catalog.image_match_review.psycopg.connect", return_value=connection_context):
            with self.assertRaisesRegex(PermissionError, "cantidad pendiente cambió"):
                decide_image_candidates_bulk(
                    1, "rejected", "isa", "Lote exacto revisado", DatabaseConfig(), "secret"
                )


if __name__ == "__main__":
    unittest.main()
