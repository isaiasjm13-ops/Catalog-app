from __future__ import annotations

import json
import tempfile
import unittest
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

from unittest import mock

from perfect_catalog.canonical import canonical_json, canonical_sha256, normalize_reference
from perfect_catalog.config import DatabaseConfig
from perfect_catalog.import_context import is_company_brand_allowed
from perfect_catalog.importer import (
    EXPECTED_HEADERS,
    analyze_headers,
    approval_fingerprint,
    build_product_diff,
    future_product_id,
    list_plan_update_diffs,
    plan_item_hash,
    plan_hash,
    prepare_rows,
    validate_pilot_row_count,
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
    def test_company_brand_policy_is_centralized(self) -> None:
        self.assertTrue(is_company_brand_allowed("KMC", "A1"))
        self.assertFalse(is_company_brand_allowed("KMC", "NATSUKI"))
        self.assertFalse(is_company_brand_allowed("PERFECT", "NATSUKI"))
        self.assertTrue(is_company_brand_allowed("PERFECT", "MASAKI"))
        self.assertTrue(is_company_brand_allowed("NATSUKI", "NATSUKI"))
        self.assertFalse(is_company_brand_allowed("NATSUKI", "MASAKI"))
        self.assertFalse(is_company_brand_allowed("MASAKI", "MASAKI"))
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
    def test_existing_product_diff_keeps_empty_values(self) -> None:
        diffs = build_product_diff(
            {
                "name_original": "Viejo", "name_normalized": "VIEJO",
                "category_path": "Motor", "variant_count_observed": 1,
            },
            {
                "name_original": "Nuevo", "name_normalized": "NUEVO",
                "category_path": "", "variant_count_observed": 1,
            },
        )
        actions = {item["field"]: item["action"] for item in diffs}
        self.assertEqual(actions["name_original"], "UPDATE")
        self.assertEqual(actions["category_path"], "KEEP_EXISTING")
        self.assertEqual(actions["variant_count_observed"], "NO_CHANGE")
    def test_headers_and_row_count_are_preserved(self) -> None:
        headers = validate_headers(EXPECTED_HEADERS)
        rows = prepare_rows("Synthetic", headers, [synthetic_row()], [2])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].source_row_number, 2)
        self.assertEqual(list(rows[0].raw_values), list(EXPECTED_HEADERS))

    def test_inventory_columns_are_ignored_for_catalog_scope(self) -> None:
        row = prepare_rows("Synthetic", EXPECTED_HEADERS, [synthetic_row()], [2])[0]
        self.assertIsNone(row.normalized["quantity_on_hand"])
        self.assertIsNone(row.normalized["quantity_available"])
        self.assertIsNone(row.normalized["currency"])
        self.assertIsNone(row.normalized["uom_original"])
        self.assertNotIn("quantity_on_hand_invalid", {issue["code"] for issue in row.issue_specs})

    def test_odoo_thumbnail_is_ignored_in_favor_of_approved_image_workflow(self) -> None:
        row = prepare_rows("Synthetic", EXPECTED_HEADERS, [synthetic_row()], [2])[0]
        self.assertEqual(row.normalized["image_status"], "not_exported")
        self.assertNotIn("image_absent", {issue["code"] for issue in row.issue_specs})

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

    def test_operational_update_date_is_not_normalized(self) -> None:
        row = prepare_rows("Synthetic", EXPECTED_HEADERS, [synthetic_row()], [2])[0]
        self.assertEqual(row.raw_excel_serials, {})
        self.assertIsNone(row.normalized["source_updated_at"])
        self.assertNotIn("excel_date_unconverted", {issue["code"] for issue in row.issue_specs})

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

    def test_reordered_headers_are_accepted_and_reported(self) -> None:
        headers = tuple(reversed(EXPECTED_HEADERS))
        contract = analyze_headers(headers)
        self.assertTrue(contract.reordered)
        self.assertEqual(contract.missing_optional, ())

    def test_known_header_case_variations_still_map_to_canonical_fields(self) -> None:
        headers = tuple(header.upper() for header in EXPECTED_HEADERS)
        row = prepare_rows("Synthetic", validate_headers(headers), [synthetic_row()], [2])[0]
        self.assertEqual(row.normalized["internal_reference_original"], "001-A-00")
        self.assertEqual(row.normalized["name_original"], "EMPAQUE SINTÉTICO A")

    def test_optional_columns_can_be_missing_without_inventing_values(self) -> None:
        headers = ("Referencia interna", "Nombre")
        contract = analyze_headers(headers)
        row = prepare_rows("Synthetic", contract.headers, [["001-A", "Pieza mínima"]], [2])[0]
        self.assertIn("Cantidad real", contract.missing_optional)
        self.assertIsNone(row.normalized["quantity_on_hand"])
        self.assertEqual(row.normalized["image_status"], "not_exported")
        self.assertNotIn("quantity_on_hand_invalid", {issue["code"] for issue in row.issue_specs})
        self.assertNotIn("image_absent", {issue["code"] for issue in row.issue_specs})

    def test_unknown_columns_are_preserved_in_raw_values(self) -> None:
        headers = EXPECTED_HEADERS + ("Campo nuevo de Odoo",)
        contract = analyze_headers(headers)
        row = prepare_rows("Synthetic", contract.headers, [synthetic_row() + ["evidencia"]], [2])[0]
        self.assertEqual(contract.unknown, ("Campo nuevo de Odoo",))
        self.assertEqual(row.raw_values["Campo nuevo de Odoo"], "evidencia")

    def test_name_enrichment_preserves_additional_reference_as_pending_evidence(self) -> None:
        headers = ("Referencia interna", "Nombre", "Referencias Adicionales", "Cantidad a mano")
        row = prepare_rows(
            "Synthetic", headers,
            [["PDM-001", "PASTILLA CHEV. AVEO 04-10 DEL. [D1035-7779]", "ALT-99", 12]],
            [2],
        )[0]
        enrichment = row.normalized["name_enrichment"]
        self.assertEqual(enrichment["review_status"], "pending_review")
        self.assertEqual(enrichment["additional_references"], ["ALT-99"])
        candidates = row.normalized["reference_candidates"]
        self.assertEqual(
            [(item["reference_type"], item["value_normalized"], item["review_status"]) for item in candidates],
            [("fmsi", "D1035-7779", "pending"), ("additional", "ALT-99", "pending")],
        )
        self.assertEqual(enrichment["applications"][0]["vehicle_brand"], "Chevrolet")
        self.assertIsNone(row.normalized["quantity_on_hand"])
        self.assertNotIn("quantity_on_hand_invalid", {issue["code"] for issue in row.issue_specs})

    def test_missing_required_header_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "columnas críticas"):
            validate_headers(header for header in EXPECTED_HEADERS if header != "Referencia interna")

    def test_duplicate_normalized_header_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicados"):
            validate_headers(EXPECTED_HEADERS + ("REFERENCIA INTERNA",))

    def test_pilot_row_limit_is_explicit(self) -> None:
        validate_pilot_row_count(893, 1_000)
        with self.assertRaisesRegex(ValueError, "supera el límite"):
            validate_pilot_row_count(1_001, 1_000)


class PlanUpdateDiffPreviewTests(unittest.TestCase):
    """El operador debe ver qué cambia campo por campo antes de aplicar el plan, no solo un
    conteo. `list_plan_update_diffs` reutiliza el `field_diffs` ya calculado al generar el
    plan (`build_product_diff`), filtrado a los campos que realmente van a cambiar."""

    def _rows(self, *proposed_values_list: dict) -> list[dict]:
        rows = []
        for index, proposed in enumerate(proposed_values_list, start=1):
            rows.append({
                "import_plan_item_id": uuid.uuid5(uuid.NAMESPACE_URL, str(index)),
                "proposed_values": proposed, "filtered_count": len(proposed_values_list),
            })
        return rows

    def _query(self, rows: list[dict], **kwargs):
        cursor = mock.Mock()
        cursor.fetchall.return_value = rows
        cursor_context = mock.Mock()
        cursor_context.__enter__ = mock.Mock(return_value=cursor)
        cursor_context.__exit__ = mock.Mock(return_value=False)
        connection = mock.Mock()
        connection.cursor.return_value = cursor_context
        connection_context = mock.Mock()
        connection_context.__enter__ = mock.Mock(return_value=connection)
        connection_context.__exit__ = mock.Mock(return_value=False)
        with mock.patch("perfect_catalog.importer.psycopg.connect", return_value=connection_context):
            return list_plan_update_diffs(uuid.uuid4(), DatabaseConfig(), "secret", **kwargs)

    def test_only_fields_that_actually_change_are_shown(self) -> None:
        rows = self._rows({
            "internal_reference_original": "NK-001", "name_original": "Empaque nuevo",
            "field_diffs": [
                {"field": "name_original", "before": "Empaque viejo", "incoming": "Empaque nuevo", "action": "UPDATE"},
                {"field": "category_path", "before": "Motor", "incoming": "Motor", "action": "NO_CHANGE"},
                {"field": "variant_count_observed", "before": 2, "incoming": None, "action": "KEEP_EXISTING"},
            ],
        })
        result = self._query(rows)
        self.assertEqual(result["filtered_count"], 1)
        item = result["items"][0]
        self.assertEqual(item["internal_reference_original"], "NK-001")
        self.assertEqual(len(item["changed_fields"]), 1)
        self.assertEqual(item["changed_fields"][0], {
            "field": "name_original", "before": "Empaque viejo", "incoming": "Empaque nuevo",
        })

    def test_empty_plan_returns_zero_without_erroring(self) -> None:
        result = self._query([])
        self.assertEqual(result, {"items": [], "filtered_count": 0, "limit": 50, "offset": 0})

    def test_rejects_out_of_range_pagination(self) -> None:
        with self.assertRaises(ValueError):
            self._query([], limit=0)
        with self.assertRaises(ValueError):
            self._query([], limit=500)
        with self.assertRaises(ValueError):
            self._query([], offset=-1)


if __name__ == "__main__":
    unittest.main()
