from __future__ import annotations

import unittest
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from perfect_catalog.cli import build_parser
from perfect_catalog.publication import (
    _json_number,
    _require_sha256,
    _require_version,
    snapshot_from_record,
)


def publication_record() -> dict[str, object]:
    return {
        "product_template_id": uuid.uuid4(),
        "product_variant_id": uuid.uuid4(),
        "name_original": "Empaque de motor",
        "variant_name": "2.0 L",
        "currency_code": "USD",
        "uom_original": "Unidad",
        "source_active": True,
        "source_updated_at": datetime(2026, 8, 24, tzinfo=UTC),
        "category_path": "Todos / Empaques",
        "source_row_number": 2,
        "reference_count": 1,
        "reference_original": "001-A-00",
        "reference_normalized": "001-A-00",
        "quantity_available": Decimal("-2.50"),
        "source_import_batch_id": uuid.uuid4(),
        "has_processed_media": True,
        "brand_name": "Natsuki",
    }


class PublicationContractTests(unittest.TestCase):
    def test_snapshot_preserves_variant_identity_and_numeric_quantity(self) -> None:
        record = publication_record()
        snapshot = snapshot_from_record(record)
        self.assertEqual(snapshot["product_template_id"], str(record["product_template_id"]))
        self.assertEqual(snapshot["product_variant_id"], str(record["product_variant_id"]))
        self.assertEqual(snapshot["name_original"], "Empaque de motor — 2.0 L")
        self.assertEqual(snapshot["name_normalized"], "EMPAQUE DE MOTOR — 2.0 L")
        self.assertEqual(snapshot["quantity_available"], -2.5)
        self.assertEqual(snapshot["image_status"], "present")
        self.assertEqual(snapshot["source_updated_at"], "2026-08-24T00:00:00+00:00")

    def test_integral_decimal_remains_an_integer(self) -> None:
        self.assertEqual(_json_number(Decimal("0.000")), 0)
        self.assertEqual(_json_number(Decimal("9007199254740993")), 9007199254740993)

    def test_version_and_checksum_contracts_are_strict(self) -> None:
        self.assertEqual(_require_version("2026.08.24-r1"), "2026.08.24-r1")
        self.assertEqual(_require_sha256("A" * 64), "a" * 64)
        for invalid in ("", "con espacio", "/ruta", "x" * 81):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    _require_version(invalid)
        with self.assertRaises(ValueError):
            _require_sha256("abc")

    def test_release_cli_commands_require_explicit_evidence(self) -> None:
        parser = build_parser()
        plan_id = str(uuid.uuid4())
        release_id = str(uuid.uuid4())
        build = parser.parse_args(
            [
                "build-release", plan_id, "--fingerprint", "a" * 64,
                "--version", "v1", "--actor", "qa", "--reason", "revisado",
            ]
        )
        publish = parser.parse_args(
            [
                "publish-release", release_id, "--snapshot-sha256", "b" * 64,
                "--actor", "qa", "--reason", "aprobado",
            ]
        )
        archive = parser.parse_args(
            [
                "archive-release", release_id, "--snapshot-sha256", "b" * 64,
                "--actor", "qa", "--reason", "sustituido",
            ]
        )
        self.assertEqual(build.command, "build-release")
        self.assertEqual(publish.command, "publish-release")
        self.assertEqual(archive.command, "archive-release")


if __name__ == "__main__":
    unittest.main()
