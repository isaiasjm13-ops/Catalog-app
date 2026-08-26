import io
import unittest
import uuid
import zipfile

from perfect_catalog.catalog_exports import export_rows_from_release, generate_catalog_pdf, generate_catalog_pptx
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
    release = {"brand_id": brand_id, "version": "synthetic-v1", "definition": definition}
    release["snapshot_sha256"] = release_snapshot_sha256(brand_id, release["version"], definition, [item])
    return release, [item]


class CatalogExportTests(unittest.TestCase):
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
