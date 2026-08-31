from __future__ import annotations

import copy
import io
import unittest
import uuid
from contextlib import redirect_stderr
from datetime import UTC, datetime
from unittest.mock import Mock, patch

from perfect_catalog.application import (
    _apply_plan_in_connection,
    _insert_vehicle_applications,
    assert_applicable_items,
    verify_plan_integrity,
)
from perfect_catalog.cli import build_parser
from perfect_catalog.importer import (
    CONTRACT_VERSION,
    RULES_VERSION,
    approval_fingerprint,
    plan_hash,
    plan_item_hash,
)


def make_item(
    plan_id: uuid.UUID,
    file_id: uuid.UUID,
    row_id: uuid.UUID,
    product_id: uuid.UUID,
    order: int,
    operation: str,
) -> dict[str, object]:
    proposed = (
        {
            "name_original": "Synthetic product",
            "internal_reference_original": "PT-001",
        }
        if operation == "create"
        else {
            "quantity_on_hand": 0,
            "quantity_available": -1,
            "uom_original": "Units",
        }
    )
    item: dict[str, object] = {
        "import_plan_item_id": uuid.uuid5(plan_id, f"item:{order}:{operation}"),
        "import_plan_id": plan_id,
        "import_file_id": file_id,
        "item_order": order,
        "staging_row_id": row_id,
        "resolved_product_template_id": None,
        "resolved_product_variant_id": None,
        "planned_product_template_id": product_id,
        "planned_product_variant_id": None,
        "operation_type": operation,
        "before_values": {},
        "proposed_values": proposed,
        "issues": [],
        "requires_review": True,
    }
    item["item_sha256"] = plan_item_hash(item)
    return item


def make_plan() -> tuple[dict[str, object], list[dict[str, object]], str]:
    plan_id = uuid.uuid4()
    file_id = uuid.uuid4()
    row_id = uuid.uuid4()
    product_id = uuid.uuid4()
    file_sha = "a" * 64
    items = [
        make_item(plan_id, file_id, row_id, product_id, 1, "create"),
        make_item(plan_id, file_id, row_id, product_id, 2, "inventory_snapshot"),
    ]
    digest = plan_hash(file_sha, items)
    fingerprint = approval_fingerprint(file_sha, digest)
    plan: dict[str, object] = {
        "import_plan_id": plan_id,
        "import_file_id": file_id,
        "file_sha256": file_sha,
        "registered_file_sha256": file_sha,
        "contract_version": CONTRACT_VERSION,
        "rules_version": RULES_VERSION,
        "plan_sha256": digest,
        "approval_fingerprint_sha256": fingerprint,
        "generated_at": datetime.now(UTC),
    }
    return plan, items, fingerprint


class PlanIntegrityTests(unittest.TestCase):
    def test_exact_plan_and_fingerprint_pass(self) -> None:
        plan, items, fingerprint = make_plan()
        verify_plan_integrity(plan, items, fingerprint)
        assert_applicable_items(items)

    def test_changed_item_is_rejected_even_with_original_fingerprint(self) -> None:
        plan, items, fingerprint = make_plan()
        changed = copy.deepcopy(items)
        changed[0]["proposed_values"]["name_original"] = "Tampered"  # type: ignore[index]
        with self.assertRaisesRegex(RuntimeError, "hash persistido"):
            verify_plan_integrity(plan, changed, fingerprint)

    def test_wrong_fingerprint_is_rejected(self) -> None:
        plan, items, _ = make_plan()
        with self.assertRaises(PermissionError):
            verify_plan_integrity(plan, items, "f" * 64)

    def test_non_hexadecimal_fingerprint_is_rejected(self) -> None:
        plan, items, _ = make_plan()
        with self.assertRaisesRegex(ValueError, "64 caracteres"):
            verify_plan_integrity(plan, items, "not-a-fingerprint")

    def test_plan_from_old_rules_requires_regeneration(self) -> None:
        plan, items, _ = make_plan()
        plan["rules_version"] = "normalization-v0.2"
        digest = plan_hash(
            plan["file_sha256"],  # type: ignore[arg-type]
            items,
            contract_version=plan["contract_version"],  # type: ignore[arg-type]
            rules_version=plan["rules_version"],  # type: ignore[arg-type]
        )
        fingerprint = approval_fingerprint(
            plan["file_sha256"],  # type: ignore[arg-type]
            digest,
            contract_version=plan["contract_version"],  # type: ignore[arg-type]
            rules_version=plan["rules_version"],  # type: ignore[arg-type]
        )
        plan["plan_sha256"] = digest
        plan["approval_fingerprint_sha256"] = fingerprint
        with self.assertRaisesRegex(RuntimeError, "versiones"):
            verify_plan_integrity(plan, items, fingerprint)

    def test_immediately_previous_rules_remain_verifiable(self) -> None:
        plan, items, _ = make_plan()
        plan["rules_version"] = "normalization-v0.3"
        digest = plan_hash(
            plan["file_sha256"], items,
            contract_version=plan["contract_version"], rules_version=plan["rules_version"],
        )
        fingerprint = approval_fingerprint(
            plan["file_sha256"], digest,
            contract_version=plan["contract_version"], rules_version=plan["rules_version"],
        )
        plan["plan_sha256"] = digest
        plan["approval_fingerprint_sha256"] = fingerprint
        verify_plan_integrity(plan, items, fingerprint)

    def test_unsupported_update_is_rejected_before_writes(self) -> None:
        plan, items, _ = make_plan()
        items[0]["operation_type"] = "update"
        with self.assertRaisesRegex(NotImplementedError, "update"):
            assert_applicable_items(items)

    def test_snapshot_for_uncreated_product_is_rejected(self) -> None:
        _, items, _ = make_plan()
        items[1]["planned_product_template_id"] = uuid.uuid4()
        with self.assertRaisesRegex(RuntimeError, "snapshots"):
            assert_applicable_items(items)

    def test_no_change_only_plan_is_safe_to_classify(self) -> None:
        plan, items, _ = make_plan()
        item = items[0]
        item["operation_type"] = "no_change"
        item["resolved_product_template_id"] = item["planned_product_template_id"]
        assert_applicable_items([item])


class ApprovalCliTests(unittest.TestCase):
    def test_approval_and_apply_require_human_evidence(self) -> None:
        parser = build_parser()
        for command in ("approve-plan", "apply-plan"):
            with self.subTest(command=command), self.assertRaises(SystemExit):
                with redirect_stderr(io.StringIO()):
                    parser.parse_args([command, str(uuid.uuid4())])
            args = parser.parse_args(
                [
                    command,
                    str(uuid.uuid4()),
                    "--fingerprint",
                    "a" * 64,
                    "--actor",
                    "reviewer",
                    "--reason",
                    "pilot reviewed",
                ]
            )
            self.assertEqual(args.actor, "reviewer")


class ApplyIdempotencyTests(unittest.TestCase):
    def test_applied_plan_returns_without_executing_another_write(self) -> None:
        plan, items, fingerprint = make_plan()
        plan["plan_status"] = "applied"
        plan["applied_by"] = "reviewer"
        connection = Mock()
        with (
            patch("perfect_catalog.application._load_plan", return_value=plan),
            patch("perfect_catalog.application._load_plan_items", return_value=items),
        ):
            result = _apply_plan_in_connection(
                connection,
                plan["import_plan_id"],  # type: ignore[arg-type]
                fingerprint,
                "reviewer",
                "retry verification",
                verify_source=False,
            )
        self.assertEqual(result["status"], "already_applied")
        connection.execute.assert_not_called()


class VehicleApplicationMaterializationTests(unittest.TestCase):
    def test_parser_suggestion_becomes_reviewable_vehicle_candidate(self) -> None:
        plan, items, _ = make_plan()
        item = items[0]
        item["proposed_values"]["name_enrichment"] = {  # type: ignore[index]
            "parser_version": "vehicle-name-suggestions-v2",
            "applications": [{
                "vehicle_brand": "Toyota", "model_suggestion": "Corolla",
                "years": {"from": 2010, "to": 2015}, "positions": ["delantero"],
                "engines": ["1.8L"], "confidence": 0.88,
            }],
        }
        connection = Mock()
        empty = Mock(); empty.fetchone.return_value = None
        connection.execute.side_effect = [empty, Mock(), empty, Mock(), Mock()]
        count = _insert_vehicle_applications(connection, plan, item)
        self.assertEqual(count, 1)
        sql = "\n".join(str(call.args[0]) for call in connection.execute.call_args_list)
        self.assertIn("vehicle_make", sql)
        self.assertIn("vehicle_model", sql)
        self.assertIn("product_application_candidate", sql)
        candidate_parameters = connection.execute.call_args_list[-1].args[1]
        self.assertIn('"engines": ["1.8L"]', candidate_parameters[-1])


if __name__ == "__main__":
    unittest.main()
