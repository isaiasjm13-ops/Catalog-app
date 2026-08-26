import unittest
import uuid

from perfect_catalog.image_match_review import MATCH_ALGORITHM, exact_image_candidates


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


if __name__ == "__main__":
    unittest.main()
