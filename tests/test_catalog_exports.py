import io
import json
import tempfile
import unittest
import uuid
import zipfile
from pathlib import Path

from perfect_catalog.catalog_exports import export_rows_from_release, generate_catalog_pdf, generate_catalog_pptx
from perfect_catalog.catalog_export_job import build_catalog_bundle
from perfect_catalog.cli import build_parser
from perfect_catalog.releases import RELEASE_HASH_ALGORITHM, SNAPSHOT_SCHEMA_VERSION, product_snapshot_sha256, release_snapshot_sha256


def fixture_release():
    brand_id, template_id = uuid.uuid4(), uuid.uuid4()
    data = {
        "product_template_id": str(template_id), "product_variant_id": None,
        "internal_reference_original": "NK-001", "internal_reference_normalized": "NK-001",
        "name_original": "Empaque de motor", "name_normalized": "EMPAQUE DE MOTOR",
        "category_path": "Motor / Empaques", "brand": "Natsuki", "quantity_available": 0,
    }
    item = {"item_order": 1, "product_template_id": template_id, "product_variant_id": None,
            "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION, "snapshot_data": data,
            "snapshot_sha256": product_snapshot_sha256(data)}
    definition = {"snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION, "release_hash_algorithm": RELEASE_HASH_ALGORITHM,
                  "source_kind": "applied_catalog", "item_count": 1, "source_plan_id": str(uuid.uuid4()),
                  "source_import_batch_id": str(uuid.uuid4()), "source_plan_fingerprint_sha256": "a"*64,
                  "contract_version": "test-v1", "rules_version": "test-v1", "selection": {}}
    release = {"catalog_release_id": uuid.uuid4(), "brand_id": brand_id, "version": "synthetic-v1", "status": "published", "definition": definition}
    release["snapshot_sha256"] = release_snapshot_sha256(brand_id, release["version"], definition, [item])
    return release, [item]


class CatalogExportTests(unittest.TestCase):
    def test_cli_exposes_export_catalog_with_repeatable_formats(self) -> None:
        release_id = uuid.uuid4()
        args = build_parser().parse_args([
            "export-catalog", str(release_id), "--output-dir", "out",
            "--format", "pdf", "--format", "indesign-json", "--prompt-password",
        ])
        self.assertEqual(args.release_id, release_id)
        self.assertEqual(args.formats, ["pdf", "indesign-json"])

    def test_adapter_revalidates_release_and_rejects_tampering(self) -> None:
        release, items = fixture_release()
        rows = export_rows_from_release(release, items)
        self.assertEqual(rows[0]["internal_reference_original"], "NK-001")
        release["snapshot_sha256"] = "0"*64
        with self.assertRaisesRegex(ValueError, "snapshot_sha256"):
            export_rows_from_release(release, items)

    def test_generated_pdf_and_pptx_are_valid_containers_with_content(self) -> None:
        release, items = fixture_release()
        rows = export_rows_from_release(release, items)
        pdf = generate_catalog_pdf(rows, {"title": "Catálogo sintético", "columns_per_row": 3})
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertIn(b"%%EOF", pdf[-64:])
        pptx = generate_catalog_pptx(rows, {"title": "Catálogo sintético", "columns_per_row": 3})
        self.assertTrue(pptx.startswith(b"PK"))
        with zipfile.ZipFile(io.BytesIO(pptx)) as archive:
            slides = [name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")]
        self.assertGreaterEqual(len(slides), 2)

    def test_pdf_escapes_untrusted_snapshot_text(self) -> None:
        release, items = fixture_release()
        rows = export_rows_from_release(release, items)
        rows[0]["name_original"] = "Empaque <desconocido> & seguro"
        self.assertTrue(generate_catalog_pdf(rows).startswith(b"%PDF-"))

    def test_bundle_writes_digital_exports_indesign_snapshot_and_manifest(self) -> None:
        release, items = fixture_release()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "bundle"
            result = build_catalog_bundle(
                release, items, output,
                config={"title": "Catálogo verificable", "columns_per_row": 2},
            )
            self.assertEqual([entry["format"] for entry in result["files"]], ["pdf", "pptx", "indesign-json"])
            self.assertTrue((output / result["manifest"]).is_file())
            manifest = json.loads((output / result["manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["release"]["snapshot_sha256"], release["snapshot_sha256"])
            snapshot_entry = next(item for item in result["files"] if item["format"] == "indesign-json")
            snapshot = json.loads((output / snapshot_entry["filename"]).read_text(encoding="utf-8"))
            self.assertEqual(snapshot["schema"], "perfect-catalog.indesign-snapshot.v1")
            self.assertEqual(snapshot["products"][0]["internal_reference_original"], "NK-001")

    def test_bundle_refuses_drafts_and_nonempty_destinations(self) -> None:
        release, items = fixture_release()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "bundle"
            release["status"] = "draft"
            with self.assertRaisesRegex(PermissionError, "publicado"):
                build_catalog_bundle(release, items, output)
            release["status"] = "published"
            output.mkdir()
            (output / "user-file.txt").write_text("preservar", encoding="utf-8")
            with self.assertRaisesRegex(FileExistsError, "no está vacío"):
                build_catalog_bundle(release, items, output)
