from __future__ import annotations

import io
import unittest
import uuid
from contextlib import redirect_stderr

from perfect_catalog.cli import build_parser
from perfect_catalog.reviews import (
    _require_decision,
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

    def test_decision_and_hash_contracts_are_strict(self) -> None:
        self.assertEqual(_require_decision(" APPROVE "), "approve")
        self.assertEqual(_require_sha256("A" * 64, "review_sha256"), "a" * 64)
        with self.assertRaises(ValueError):
            _require_decision("activate")
        with self.assertRaises(ValueError):
            _require_sha256("abc", "review_sha256")

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


if __name__ == "__main__":
    unittest.main()
