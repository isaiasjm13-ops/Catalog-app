from __future__ import annotations

import json
import tempfile
import unittest
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from perfect_catalog.canonical import canonical_json, canonical_sha256, normalize_reference
from perfect_catalog.config import DatabaseConfig
from perfect_catalog.importer import (
    EXPECTED_HEADERS,
    approval_fingerprint,
    assert_apply_allowed,
    future_product_id,
    plan_item_hash,
    plan_hash,
    prepare_rows,
    validate_headers,
)


def synthetic_row(**overrides: object) -> list[object]:
    values: dict[str, object] = {
        "Moneda": "USD",
        "Estado de la actividad": None,
        "Categoría de producto": "Todos / Empaques",
        "Favorito": False,
        "Nombre": "EMPAQUE SINTÉTICO A",
        "Referencia interna": "001-A-00",
        "# Variantes de producto": 1,
        "Cantidad real": -2,
        "Unidad de medida": "Unidades",
        "Cantidad disponible": 0,
        "Imagen 128": None,
        "Última actualización el": 46000.5,
        "Mostrar botón de estado de cantidad real": True,
    }
    values.update(overrides)
    return [values[header] for header in EXPECTED_HEADERS]


class CanonicalTests(unittest.TestCase):
    def test_hash_is_stable_for_key_order(self) -> None:
        self.assertEqual(canonical_sha256({"b": 2, "a": 1}), canonical_sha256({"a": 1, "b": 2}))

    def test_uuid_serialization_is_stable(self) -> None:
        value = uuid.UUID("12345678-1234-5678-1234-567812345678")
        self.assertEqual(canonical_json({"id": value}), '{"id":"12345678-1234-5678-1234-567812345678"}')

    def test_date_and_time_serialization_is_stable(self) -> None:
        value = {
            "date": date(2026, 8, 24),
            "datetime": datetime(2026, 8, 24, 15, 30, 45),
            "time": time(15, 30, 45, 123456),
        }
        self.assertEqual(
            canonical_json(value),
            '{"date":"2026-08-24","datetime":"2026-08-24T15:30:45","time":"15:30:45.123456"}',
        )

    def test_decimal_serialization_is_stable(self) -> None:
        self.assertEqual(canonical_json({"amount": Decimal("10.5000")}), '{"amount":"10.5000"}')

    def test_same_content_has_equal_hashes(self) -> None:
        first = {"nested": [{"value": Decimal("2.50")}], "id": uuid.UUID(int=1)}
        second = {"id": uuid.UUID(int=1), "nested": ({"value": Decimal("2.50")},)}
        self.assertEqual(canonical_sha256(first), canonical_sha256(second))

    def test_plan_item_hash_accepts_all_plan_uuids(self) -> None:
        item = {
            "import_plan_item_id": uuid.UUID(int=1),
            "import_plan_id": uuid.UUID(int=2),
            "import_file_id": uuid.UUID(int=3),
            "staging_row_id": uuid.UUID(int=4),
            "resolved_product_template_id": uuid.UUID(int=5),
            "resolved_product_variant_id": uuid.UUID(int=6),
            "planned_product_template_id": uuid.UUID(int=7),
            "planned_product_variant_id": uuid.UUID(int=8),
            "item_order": 1,
            "operation_type": "create",
            "before_values": {},
            "proposed_values": {"quantity": Decimal("1.00")},
            "issues": [],
            "requires_review": True,
        }
        first = plan_item_hash(item)
        second = plan_item_hash(dict(reversed(list(item.items()))))
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)

    def test_reference_preserves_zeroes_hyphens_and_inner_spacing(self) -> None:
        self.assertEqual(normalize_reference(" 001-a-00 "), "001-A-00")
        self.assertEqual(normalize_reference("A  01"), "A  01")

    def test_future_uuid_is_stable_inside_exact_plan(self) -> None:
        plan_id = uuid.uuid4()
        self.assertEqual(future_product_id(plan_id, "001-A"), future_product_id(plan_id, "001-A"))

    def test_plan_hash_and_fingerprint_are_stable(self) -> None:
        items = [{"item_sha256": "a" * 64}, {"item_sha256": "b" * 64}]
        first = plan_hash("c" * 64, items)
        second = plan_hash("c" * 64, items)
        self.assertEqual(first, second)
        self.assertEqual(
            approval_fingerprint("c" * 64, first),
            approval_fingerprint("c" * 64, second),
        )


class RowPreparationTests(unittest.TestCase):
    def test_headers_and_row_count_are_preserved(self) -> None:
        headers = validate_headers(EXPECTED_HEADERS)
        rows = prepare_rows("Synthetic", headers, [synthetic_row()], [2])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].source_row_number, 2)
        self.assertEqual(list(rows[0].raw_values), list(EXPECTED_HEADERS))

    def test_negative_stock_is_valid(self) -> None:
        row = prepare_rows("Synthetic", EXPECTED_HEADERS, [synthetic_row()], [2])[0]
        self.assertEqual(row.normalized["quantity_on_hand"], -2)
        self.assertNotIn("quantity_on_hand_invalid", {issue["code"] for issue in row.issue_specs})

    def test_empty_image_continues_without_base64_logging(self) -> None:
        row = prepare_rows("Synthetic", EXPECTED_HEADERS, [synthetic_row()], [2])[0]
        self.assertEqual(row.normalized["image_status"], "absent")
        self.assertIn("image_absent", {issue["code"] for issue in row.issue_specs})

    def test_base64_is_not_copied_to_structural_metadata_or_issues(self) -> None:
        payload = "U1lOVEhFVElDX0lNQUdF" * 20
        row = prepare_rows(
            "Synthetic",
            EXPECTED_HEADERS,
            [synthetic_row(**{"Imagen 128": payload})],
            [2],
        )[0]
        public_evidence = json.dumps(
            {"metadata": row.structural_metadata, "issues": row.issue_specs, "normalized": row.normalized},
            ensure_ascii=False,
        )
        self.assertNotIn(payload, public_evidence)
        self.assertFalse(row.structural_metadata["image"]["decoded"])

    def test_excel_date_remains_serial_with_warning(self) -> None:
        row = prepare_rows("Synthetic", EXPECTED_HEADERS, [synthetic_row()], [2])[0]
        self.assertEqual(row.raw_excel_serials["Última actualización el"], 46000.5)
        self.assertIsNone(row.normalized["source_updated_at"])
        self.assertIn("excel_date_unconverted", {issue["code"] for issue in row.issue_specs})

    def test_duplicate_names_do_not_merge_references(self) -> None:
        rows = prepare_rows(
            "Synthetic",
            EXPECTED_HEADERS,
            [synthetic_row(), synthetic_row(**{"Referencia interna": "002-B-00"})],
            [2, 3],
        )
        self.assertEqual(rows[0].normalized["name_normalized"], rows[1].normalized["name_normalized"])
        self.assertNotEqual(
            rows[0].normalized["internal_reference_normalized"],
            rows[1].normalized["internal_reference_normalized"],
        )

    def test_source_active_stays_unknown(self) -> None:
        row = prepare_rows("Synthetic", EXPECTED_HEADERS, [synthetic_row()], [2])[0]
        self.assertIsNone(row.normalized["source_active"])


class ApplyGateTests(unittest.TestCase):
    @patch("perfect_catalog.importer.inspect_plan")
    def test_unapproved_plan_is_rejected(self, mocked_inspect: object) -> None:
        mocked_inspect.return_value = {"plan_status": "awaiting_review"}
        with self.assertRaises(PermissionError):
            assert_apply_allowed(uuid.uuid4(), DatabaseConfig(), "synthetic-secret")


if __name__ == "__main__":
    unittest.main()
