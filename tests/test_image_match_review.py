import unittest
import uuid
from unittest.mock import Mock, patch

from perfect_catalog.config import DatabaseConfig
from perfect_catalog.image_match_review import (
    MATCH_ALGORITHM, decide_image_candidate, decide_image_candidates_bulk, exact_image_candidates,
)


class ImageMatchReviewTests(unittest.TestCase):
    COMPANY_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")

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

    def test_individual_decision_uses_advisory_lock_for_append_only_candidate(self) -> None:
        candidate_id = uuid.uuid4()
        cursor = Mock(); cursor.fetchone.side_effect = [{"evidence_sha256": "a" * 64}, None]
        cursor_context = Mock(); cursor_context.__enter__ = Mock(return_value=cursor); cursor_context.__exit__ = Mock(return_value=False)
        connection = Mock(); connection.cursor.return_value = cursor_context
        connection_context = Mock(); connection_context.__enter__ = Mock(return_value=connection); connection_context.__exit__ = Mock(return_value=False)
        with patch("perfect_catalog.image_match_review.psycopg.connect", return_value=connection_context):
            result = decide_image_candidate(
                candidate_id, "a" * 64, "approved", "isa", "Revisión exacta",
                DatabaseConfig(), "secret", company_id=self.COMPANY_ID,
            )
        self.assertEqual(result, {"status": "approved"})
        connection.execute.assert_called_once_with(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 4))", (str(candidate_id),)
        )
        self.assertNotIn("FOR UPDATE", "\n".join(str(call.args[0]) for call in cursor.execute.call_args_list))

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
                2, "approved", "isa", "Lote exacto revisado", DatabaseConfig(), "secret",
                company_id=self.COMPANY_ID,
            )
        self.assertEqual(result, {"status": "bulk_approved", "count": 2})
        insert_calls = [call for call in cursor.execute.call_args_list if "INSERT INTO" in call.args[0]]
        self.assertEqual(len(insert_calls), 2)
        self.assertEqual([call.args[1][3] for call in insert_calls], ["a" * 64, "b" * 64])
        connection.execute.assert_any_call(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 3))",
            ("perfect_catalog.image_product_candidate.bulk_decision",),
        )
        selection_sql = next(
            call.args[0] for call in cursor.execute.call_args_list
            if "FROM perfect_catalog.image_product_candidate AS c" in call.args[0]
        )
        self.assertNotIn("FOR UPDATE", selection_sql)

    def test_bulk_decision_rejects_if_pending_count_changed(self) -> None:
        cursor = Mock(); cursor.fetchall.return_value = []
        cursor_context = Mock(); cursor_context.__enter__ = Mock(return_value=cursor); cursor_context.__exit__ = Mock(return_value=False)
        connection = Mock(); connection.cursor.return_value = cursor_context
        connection_context = Mock(); connection_context.__enter__ = Mock(return_value=connection); connection_context.__exit__ = Mock(return_value=False)
        with patch("perfect_catalog.image_match_review.psycopg.connect", return_value=connection_context):
            with self.assertRaisesRegex(PermissionError, "cantidad pendiente cambió"):
                decide_image_candidates_bulk(
                    1, "rejected", "isa", "Lote exacto revisado", DatabaseConfig(), "secret",
                    company_id=self.COMPANY_ID,
                )


if __name__ == "__main__":
    unittest.main()
