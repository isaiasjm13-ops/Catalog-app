from __future__ import annotations

import unittest
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest import mock

from perfect_catalog import publication as publication_module
from perfect_catalog.cli import build_parser
from perfect_catalog.publication import (
    _require_sha256,
    _require_version,
    load_published_release,
    snapshot_from_record,
)
from perfect_catalog.brand_profiles import visual_profile
from perfect_catalog.canonical import json_compatible


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
        "cross_references": [
            {"reference_type": "oem", "value_original": "44310-0K020",
             "value_normalized": "44310-0K020", "confidence": 0.82},
            {"reference_type": "fmsi", "value_original": "D1035-7779",
             "value_normalized": "D1035-7779", "confidence": 0.82},
            {"reference_type": "additional", "value_original": "ALT-99",
             "value_normalized": "ALT-99", "confidence": 1.0},
        ],
        "application_details": [
            {"make": "Toyota", "model": "Corolla", "year_from": 2010,
             "year_to": 2015, "position": "delantero", "confidence": 0.9,
             "notes": '{"engines":["1.8L"],"positions":["delantero"]}'}
        ],
    }


class PublicationContractTests(unittest.TestCase):
    def test_snapshot_preserves_identity_and_excludes_commercial_values(self) -> None:
        record = publication_record()
        snapshot = snapshot_from_record(record)
        self.assertEqual(snapshot["product_template_id"], str(record["product_template_id"]))
        self.assertEqual(snapshot["product_variant_id"], str(record["product_variant_id"]))
        self.assertEqual(snapshot["name_original"], "Empaque de motor — 2.0 L")
        self.assertEqual(snapshot["name_normalized"], "EMPAQUE DE MOTOR — 2.0 L")
        self.assertIsNone(snapshot["quantity_available"])
        self.assertIsNone(snapshot["currency"])
        self.assertIsNone(snapshot["uom_original"])
        self.assertEqual(snapshot["image_status"], "present")
        self.assertEqual(snapshot["vehicle_makes"], ["Toyota"])
        self.assertEqual(snapshot["vehicle_make"], "Toyota")
        self.assertEqual(snapshot["piece_type"], "Empaques")
        self.assertEqual(snapshot["engine_types"], ["1.8L"])
        self.assertEqual(snapshot["oem_references"], ["44310-0K020"])
        self.assertEqual(snapshot["fmsi_references"], ["D1035-7779"])
        self.assertEqual(snapshot["additional_references"], ["ALT-99"])
        self.assertEqual(snapshot["applications"], ["Toyota Corolla 2010–2015 · delantero · 1.8L"])
        self.assertEqual(snapshot["source_updated_at"], "2026-08-24T00:00:00+00:00")
        self.assertEqual(snapshot["variant_images"], [])

    def test_snapshot_carries_the_ordered_gallery_of_extra_photos(self) -> None:
        record = publication_record()
        record["approved_variant_images"] = [
            {"storage_relpath": "objects/aa/aaaa.jpg", "sha256": "a" * 64, "media_type": "image/jpeg", "variant_index": 2},
            {"storage_relpath": "objects/bb/bbbb.jpg", "sha256": "b" * 64, "media_type": "image/jpeg", "variant_index": 3},
        ]
        snapshot = snapshot_from_record(record)
        self.assertEqual([image["variant_index"] for image in snapshot["variant_images"]], [2, 3])
        self.assertEqual(snapshot["variant_images"][0]["storage_relpath"], "objects/aa/aaaa.jpg")

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
                "--version", "v1", "--brand", "NATSUKI",
                "--actor", "qa", "--reason", "revisado",
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

    def test_visual_profile_is_jsonb_compatible_before_release_hashing(self) -> None:
        profile = visual_profile({
            "code": "NATSUKI", "display_name": "Natsuki",
            "minimum_font_size_pt": Decimal("12.00"),
            "body_line_height": Decimal("1.80"),
            "watermark_opacity": Decimal("0.050"),
        })
        normalized = json_compatible(profile)
        self.assertEqual(normalized["minimum_font_size_pt"], "12.00")
        self.assertEqual(normalized["body_line_height"], "1.80")
        self.assertEqual(normalized["watermark_opacity"], "0.050")


class LoadPublishedReleaseCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        publication_module._PUBLISHED_RELEASE_CACHE.clear()

    def _connection_context(self) -> mock.MagicMock:
        connection = mock.MagicMock()
        context = mock.MagicMock()
        context.__enter__.return_value = connection
        context.__exit__.return_value = False
        return context

    def test_second_call_reuses_cached_content_without_reverifying(self) -> None:
        release_id = uuid.uuid4()
        release = {"status": "published"}
        items = [{"item_order": 1}]
        config = mock.MagicMock()
        config.connection_kwargs.return_value = {}
        with (
            mock.patch.object(publication_module.psycopg, "connect", return_value=self._connection_context()),
            mock.patch.object(publication_module, "_load_release", return_value=(release, items)) as load_release,
            mock.patch.object(publication_module, "_verify_release") as verify_release,
            mock.patch.object(publication_module, "_current_release_status", return_value="published") as status_check,
        ):
            first = load_published_release(release_id, config, "secret")
            second = load_published_release(release_id, config, "secret")
        self.assertEqual(first, (release, items))
        self.assertEqual(second, (release, items))
        load_release.assert_called_once()
        verify_release.assert_called_once()
        status_check.assert_called_once()

    def test_cache_hit_still_rejects_a_release_archived_after_caching(self) -> None:
        release_id = uuid.uuid4()
        release = {"status": "published"}
        items = [{"item_order": 1}]
        config = mock.MagicMock()
        config.connection_kwargs.return_value = {}
        with (
            mock.patch.object(publication_module.psycopg, "connect", return_value=self._connection_context()),
            mock.patch.object(publication_module, "_load_release", return_value=(release, items)) as load_release,
            mock.patch.object(publication_module, "_verify_release"),
            mock.patch.object(publication_module, "_current_release_status", return_value="archived"),
        ):
            load_published_release(release_id, config, "secret")
            with self.assertRaises(PermissionError):
                load_published_release(release_id, config, "secret")
            self.assertNotIn(release_id, publication_module._PUBLISHED_RELEASE_CACHE)
            load_published_release(release_id, config, "secret")
        self.assertEqual(load_release.call_count, 2)


if __name__ == "__main__":
    unittest.main()
