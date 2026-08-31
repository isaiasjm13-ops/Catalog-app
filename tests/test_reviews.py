from __future__ import annotations

import io
import unittest
import uuid
from contextlib import redirect_stderr
from unittest import mock

from perfect_catalog.cli import build_parser
from perfect_catalog.config import DatabaseConfig
from perfect_catalog import reviews
from perfect_catalog.reviews import (
    _require_decision,
    _require_review_state,
    _require_sha256,
    review_evidence_sha256,
)


def review_fixture() -> tuple[dict[str, object], dict[str, object]]:
    plan_id = uuid.uuid4()
    batch_id = uuid.uuid4()
    product_id = uuid.uuid4()
    target: dict[str, object] = {
        "identity_type": "product_template",
        "public_id": product_id,
        "product_template_id": product_id,
        "product_variant_id": None,
        "source_system_id": uuid.uuid4(),
        "brand_id": uuid.uuid4(),
        "brand_name": "Natsuki",
        "name_original": "Producto de prueba",
        "variant_name": None,
        "catalog_status": "pending_review",
        "template_status": "pending_review",
        "source_row_number": 2,
        "reference": {
            "product_reference_id": uuid.uuid4(),
            "reference_type": "internal",
            "value_original": "ABC-001",
            "value_normalized": "ABC-001",
            "is_primary": True,
            "review_status": "pending",
        },
        "cross_references": [],
    }
    plan: dict[str, object] = {
        "import_plan_id": plan_id,
        "approval_fingerprint_sha256": "a" * 64,
        "import_batch_id": batch_id,
    }
    return target, plan


class ReviewContractTests(unittest.TestCase):
    def test_review_hash_is_stable_and_binds_visible_reference(self) -> None:
        target, plan = review_fixture()
        digest = review_evidence_sha256(target, plan)
        self.assertEqual(digest, review_evidence_sha256(target, plan))
        self.assertRegex(digest, r"^[0-9a-f]{64}$")
        target["reference"]["value_original"] = "ABC-002"  # type: ignore[index]
        self.assertNotEqual(digest, review_evidence_sha256(target, plan))

    def test_review_hash_binds_cross_references_and_their_status(self) -> None:
        target, plan = review_fixture()
        target["cross_references"] = [{
            "product_reference_id": uuid.uuid4(), "reference_type": "oem",
            "value_original": "44310-0K020", "value_normalized": "44310-0K020",
            "confidence": 0.82, "review_status": "pending",
        }]
        digest = review_evidence_sha256(target, plan)
        target["cross_references"][0]["value_original"] = "OTRO"  # type: ignore[index]
        self.assertNotEqual(digest, review_evidence_sha256(target, plan))

    def test_decision_and_hash_contracts_are_strict(self) -> None:
        self.assertEqual(_require_decision(" APPROVE "), "approve")
        self.assertEqual(_require_sha256("A" * 64, "review_sha256"), "a" * 64)
        with self.assertRaises(ValueError):
            _require_decision("activate")
        with self.assertRaises(ValueError):
            _require_sha256("abc", "review_sha256")
        self.assertEqual(_require_review_state(" PENDING "), "pending")
        with self.assertRaises(ValueError):
            _require_review_state("deleted")

    def test_review_cli_requires_exact_human_evidence(self) -> None:
        parser = build_parser()
        plan_id = str(uuid.uuid4())
        product_id = str(uuid.uuid4())
        inspected = parser.parse_args(
            ["inspect-reviews", plan_id, "--fingerprint", "a" * 64]
        )
        self.assertEqual(inspected.command, "inspect-reviews")
        with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):
            parser.parse_args(["review-product", plan_id, product_id])
        reviewed = parser.parse_args(
            [
                "review-product",
                plan_id,
                product_id,
                "--fingerprint",
                "a" * 64,
                "--review-sha256",
                "b" * 64,
                "--decision",
                "reject",
                "--actor",
                "reviewer",
                "--reason",
                "referencia incorrecta",
            ]
        )
        self.assertEqual(reviewed.decision, "reject")
        self.assertEqual(reviewed.actor, "reviewer")

    def test_bulk_review_rejects_changed_count_before_any_decision(self) -> None:
        connection = mock.MagicMock()
        context = mock.MagicMock()
        context.__enter__.return_value = connection
        context.__exit__.return_value = False
        with mock.patch.object(reviews.psycopg, "connect", return_value=context), mock.patch.object(
            reviews, "_review_queue_page_in_connection",
            return_value={"filtered_count": 2, "items": []},
        ), mock.patch.object(reviews, "_review_product_in_connection") as decide:
            with self.assertRaisesRegex(PermissionError, "cantidad pendiente cambió"):
                reviews.review_products_bulk(
                    uuid.uuid4(), "a" * 64, "reject", "qa", "Fuera de catálogo",
                    DatabaseConfig(), "secret", query="", expected_count=3,
                )
        decide.assert_not_called()

    def test_bulk_review_recomputes_and_decides_each_exact_identity(self) -> None:
        plan_id = uuid.uuid4()
        ids = [uuid.uuid4(), uuid.uuid4()]
        connection = mock.MagicMock()
        context = mock.MagicMock()
        context.__enter__.return_value = connection
        context.__exit__.return_value = False
        queue = {
            "filtered_count": 2,
            "items": [
                {"product_id": str(ids[0]), "review_sha256": "b" * 64},
                {"product_id": str(ids[1]), "review_sha256": "c" * 64},
            ],
        }
        decisions = [
            {"status": "rejected"}, {"status": "rejected"},
        ]
        with mock.patch.object(reviews.psycopg, "connect", return_value=context), mock.patch.object(
            reviews, "_review_queue_page_in_connection", return_value=queue,
        ), mock.patch.object(
            reviews, "_review_product_in_connection", side_effect=decisions,
        ) as decide:
            result = reviews.review_products_bulk(
                plan_id, "a" * 64, "reject", "qa", "Fuera de catálogo",
                DatabaseConfig(), "secret", query="MY", expected_count=2,
            )
        self.assertEqual(result["status"], "bulk_rejected")
        self.assertEqual(result["count"], 2)
        self.assertEqual(decide.call_count, 2)
        self.assertEqual(decide.call_args_list[0].args[2], ids[0])


if __name__ == "__main__":
    unittest.main()
