import io
import json
import hashlib
import base64
import csv
import tempfile
import unittest
from unittest import mock
import uuid
import zipfile
from pathlib import Path

from perfect_catalog.catalog_exports import export_rows_from_release, generate_catalog_html, generate_catalog_pdf, generate_catalog_pptx, generate_indesign_datamerge_csv
from perfect_catalog.catalog_export_job import (
    build_catalog_bundle,
    build_catalog_preview,
    list_operator_catalog_exports,
    resolve_catalog_download,
    verify_catalog_bundle,
)
from perfect_catalog.cli import build_parser, main as cli_main
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

    def test_cli_accepts_repeatable_exact_reference_selection(self) -> None:
        args = build_parser().parse_args([
            "export-catalog", str(uuid.uuid4()), "--output-dir", "out",
            "--reference", "NK-001", "--reference", "NK-002", "--prompt-password",
            "--theme", "classic",
        ])
        self.assertEqual(args.selected_references, ["NK-001", "NK-002"])
        self.assertEqual(args.theme, "classic")

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
        pdf = generate_catalog_pdf(
            rows, {"title": "Catálogo sintético", "columns_per_row": 3, "theme": "industrial"},
            release=release,
        )
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertIn(b"%%EOF", pdf[-64:])
        pptx = generate_catalog_pptx(
            rows, {"title": "Catálogo sintético", "columns_per_row": 3, "theme": "industrial"},
            release=release,
        )
        self.assertTrue(pptx.startswith(b"PK"))
        with zipfile.ZipFile(io.BytesIO(pptx)) as archive:
            slides = [name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")]
            slide_xml = "".join(archive.read(name).decode("utf-8") for name in slides)
        self.assertGreaterEqual(len(slides), 2)
        self.assertIn("C34A21", slide_xml)
        self.assertIn(str(release["snapshot_sha256"])[:16], slide_xml)

    def test_pdf_escapes_untrusted_snapshot_text(self) -> None:
        release, items = fixture_release()
        rows = export_rows_from_release(release, items)
        rows[0]["name_original"] = "Empaque <desconocido> & seguro"
        self.assertTrue(generate_catalog_pdf(rows).startswith(b"%PDF-"))

    def test_indesign_datamerge_csv_has_bom_quotes_lists_and_neutralizes_formulas(self) -> None:
        content = generate_indesign_datamerge_csv([{
            "internal_reference_original": "=DANGEROUS",
            "name_original": "Empaque, motor",
            "category_path": "Motor", "brand": "Natsuki",
            "applications": ["Toyota", "Honda"], "oem_references": ["+OEM"],
            "image_path": "image-safe.jpg",
        }])
        self.assertTrue(content.startswith(b"\xef\xbb\xbf"))
        row = next(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
        self.assertEqual(row["reference"], "'=DANGEROUS")
        self.assertEqual(row["name"], "Empaque, motor")
        self.assertEqual(row["applications"], "Toyota; Honda")
        self.assertEqual(row["oem_references"], "'+OEM")
        self.assertEqual(row["@image"], "image-safe.jpg")

    def test_digital_html_is_responsive_traceable_and_escapes_snapshot_text(self) -> None:
        release, items = fixture_release()
        rows = export_rows_from_release(release, items)
        rows[0]["name_original"] = '<script>alert("x")</script>'
        rows[0]["image_path"] = "image-safe.png"
        content = generate_catalog_html(
            rows, {"title": "Edición digital", "columns_per_row": 3, "theme": "industrial"}, release=release
        ).decode("utf-8")
        self.assertTrue(content.startswith("<!doctype html>"))
        self.assertIn("@media(max-width:760px)", content)
        self.assertIn(str(release["snapshot_sha256"]), content)
        self.assertIn('src="image-safe.png"', content)
        self.assertIn("--forest:#C34A21", content)
        self.assertNotIn("<script>", content)

    def test_bundle_writes_digital_exports_indesign_snapshot_and_manifest(self) -> None:
        release, items = fixture_release()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "bundle"
            result = build_catalog_bundle(
                release, items, output,
                config={"title": "Catálogo verificable", "columns_per_row": 2},
            )
            self.assertEqual([entry["format"] for entry in result["files"]], ["html", "digital-zip", "pdf", "pptx", "indesign-json", "indesign-csv", "indesign-package"])
            self.assertEqual(result["verification"]["status"], "verified")
            self.assertEqual(result["verification"]["file_count"], len(result["files"]))
            zip_entry = next(item for item in result["files"] if item["format"] == "digital-zip")
            with zipfile.ZipFile(output / zip_entry["filename"]) as digital:
                self.assertIn("index.html", digital.namelist())
                self.assertTrue(digital.read("index.html").startswith(b"<!doctype html>"))
            self.assertTrue((output / result["manifest"]).is_file())
            manifest = json.loads((output / result["manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["release"]["snapshot_sha256"], release["snapshot_sha256"])
            self.assertEqual(manifest["layout"]["theme"], "forest")
            snapshot_entry = next(item for item in result["files"] if item["format"] == "indesign-json")
            snapshot = json.loads((output / snapshot_entry["filename"]).read_text(encoding="utf-8"))
            self.assertEqual(snapshot["schema"], "perfect-catalog.indesign-snapshot.v1")
            self.assertEqual(snapshot["layout"]["template_profile"], "T4")
            self.assertEqual(snapshot["products"][0]["internal_reference_original"], "NK-001")
            package_entry = next(item for item in result["files"] if item["format"] == "indesign-package")
            with zipfile.ZipFile(output / package_entry["filename"]) as package:
                self.assertEqual(
                    set(package.namelist()),
                    {"catalog.indesign.json", "catalog.datamerge.csv", "ImportPerfectCatalog.jsx", "LEEME-INDESIGN.txt"},
                )
                self.assertEqual(
                    json.loads(package.read("catalog.indesign.json")), snapshot,
                )
                data_merge = list(csv.DictReader(io.StringIO(
                    package.read("catalog.datamerge.csv").decode("utf-8-sig")
                )))
                self.assertEqual(data_merge[0]["reference"], "NK-001")
                self.assertIn("@image", data_merge[0])
            verification = verify_catalog_bundle(output / result["manifest"])
            self.assertEqual(verification["status"], "verified")
            self.assertEqual(verification["file_count"], len(result["files"]))
            captured = io.StringIO()
            with mock.patch("sys.stdout", captured), mock.patch(
                "perfect_catalog.cli.prompt_password",
                side_effect=AssertionError("offline verification must not prompt"),
            ):
                self.assertEqual(cli_main(["verify-catalog-export", str(output / result["manifest"])]), 0)
            self.assertEqual(json.loads(captured.getvalue())["status"], "verified")

            pdf_entry = next(item for item in result["files"] if item["format"] == "pdf")
            pdf_path = output / pdf_entry["filename"]
            original_pdf = pdf_path.read_bytes()
            pdf_path.write_bytes(original_pdf + b"tampered")
            with self.assertRaisesRegex(ValueError, "no coincide"):
                verify_catalog_bundle(output / result["manifest"])
            pdf_path.write_bytes(original_pdf)
            (output / "unexpected.txt").write_text("not manifested", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "inesperados"):
                verify_catalog_bundle(output / result["manifest"])

    def test_bundle_validates_indesign_template_profile(self) -> None:
        release, items = fixture_release()
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "Perfil InDesign"):
                build_catalog_bundle(
                    release, items, Path(temporary) / "bundle",
                    formats=("indesign-json",), config={"template_profile": "UNKNOWN"},
                )
            with self.assertRaisesRegex(ValueError, "Tema editorial"):
                build_catalog_bundle(
                    release, items, Path(temporary) / "theme",
                    formats=("html",), config={"theme": "unknown"},
                )

    def test_bundle_packages_only_sha_verified_approved_images(self) -> None:
        release, items = fixture_release()
        content = b"synthetic-approved-image"
        digest = hashlib.sha256(content).hexdigest()
        data = items[0]["snapshot_data"]
        data.update({
            "image_status": True,
            "image_storage_relpath": f"objects/{digest[:2]}/{digest}.jpg",
            "image_sha256": digest,
            "image_media_type": "image/jpeg",
        })
        items[0]["snapshot_sha256"] = product_snapshot_sha256(data)
        release["snapshot_sha256"] = release_snapshot_sha256(
            release["brand_id"], release["version"], release["definition"], items
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "images" / data["image_storage_relpath"]
            source.parent.mkdir(parents=True)
            source.write_bytes(content)
            output = root / "bundle"
            result = build_catalog_bundle(
                release, items, output, formats=("html", "indesign-json"), image_root=root / "images"
            )
            image_entry = next(entry for entry in result["files"] if entry["format"] == "image")
            self.assertEqual((output / image_entry["filename"]).read_bytes(), content)
            snapshot_entry = next(entry for entry in result["files"] if entry["format"] == "indesign-json")
            snapshot = json.loads((output / snapshot_entry["filename"]).read_text(encoding="utf-8"))
            self.assertEqual(snapshot["products"][0]["image_path"], image_entry["filename"])
            zip_entry = next(entry for entry in result["files"] if entry["format"] == "digital-zip")
            with zipfile.ZipFile(output / zip_entry["filename"]) as digital:
                self.assertEqual(digital.read(image_entry["filename"]), content)
            indesign_package = next(entry for entry in result["files"] if entry["format"] == "indesign-package")
            with zipfile.ZipFile(output / indesign_package["filename"]) as package:
                self.assertEqual(package.read(image_entry["filename"]), content)

            source.write_bytes(b"tampered")
            with self.assertRaisesRegex(RuntimeError, "SHA-256"):
                build_catalog_bundle(
                    release, items, root / "tampered", formats=("indesign-json",),
                    image_root=root / "images",
                )

    def test_pdf_and_pptx_render_a_packaged_product_image(self) -> None:
        image = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
        rows = [{
            "internal_reference_original": "IMG-001", "name_original": "Producto visual",
            "category_path": "Visual", "image_path": "approved.png",
        }]
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary)
            (bundle / "approved.png").write_bytes(image)
            pdf = generate_catalog_pdf(rows, bundle_dir=bundle)
            self.assertTrue(pdf.startswith(b"%PDF-"))
            pptx = generate_catalog_pptx(rows, bundle_dir=bundle)
            with zipfile.ZipFile(io.BytesIO(pptx)) as archive:
                self.assertTrue(any(name.startswith("ppt/media/image") for name in archive.namelist()))

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

    def test_operator_history_and_downloads_are_manifest_scoped(self) -> None:
        release, items = fixture_release()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            export_id = uuid.uuid4()
            output = root / str(release["catalog_release_id"]) / str(export_id)
            result = build_catalog_bundle(release, items, output, formats=("indesign-json",))
            history = list_operator_catalog_exports(root)
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["export_id"], str(export_id))
            filename = result["files"][0]["filename"]
            self.assertEqual(
                resolve_catalog_download(root, release["catalog_release_id"], export_id, filename),
                (output / filename).resolve(),
            )
            with self.assertRaises(PermissionError):
                resolve_catalog_download(root, release["catalog_release_id"], export_id, "private.txt")
            with self.assertRaises(ValueError):
                resolve_catalog_download(root, release["catalog_release_id"], export_id, "../private.txt")

    def test_preview_revalidates_release_and_limits_rendered_products(self) -> None:
        release, items = fixture_release()
        preview = build_catalog_preview(release, items, group_by="category_path", sample_limit=1)
        self.assertEqual(preview["total_count"], 1)
        self.assertEqual(preview["sample_count"], 1)
        self.assertEqual(preview["groups"][0]["count"], 1)
        release["snapshot_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "snapshot_sha256"):
            build_catalog_preview(release, items)

    def test_selection_filter_and_secondary_group_are_manifested(self) -> None:
        release, items = fixture_release()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "bundle"
            result = build_catalog_bundle(
                release, items, output, formats=("indesign-json",),
                config={
                    "group_by": "brand", "group_by_secondary": "category_path",
                    "filter_field": "name_original", "filter_query": "empaque",
                },
            )
            self.assertEqual(result["selection"]["selected_item_count"], 1)
            self.assertEqual(result["selection"]["group_by_secondary"], "category_path")
            manifest = json.loads((output / result["manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["selection"]["filter_query"], "empaque")
            with self.assertRaisesRegex(ValueError, "ningún producto"):
                build_catalog_bundle(
                    release, items, Path(temporary) / "empty", formats=("pdf",),
                    config={"filter_field": "name_original", "filter_query": "inexistente"},
                )

    def test_manual_reference_selection_is_exact_manifested_and_rejects_typos(self) -> None:
        release, items = fixture_release()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = build_catalog_bundle(
                release, items, root / "selected", formats=("indesign-json",),
                config={"selected_references": " nk-001\nNK-001, "},
            )
            self.assertEqual(result["selection"]["selected_item_count"], 1)
            self.assertEqual(result["selection"]["selected_references"], ["nk-001"])
            self.assertRegex(result["selection"]["selected_references_sha256"], r"^[0-9a-f]{64}$")
            with self.assertRaisesRegex(ValueError, "no encontradas"):
                build_catalog_bundle(
                    release, items, root / "typo", formats=("pdf",),
                    config={"selected_references": "NK-DOES-NOT-EXIST"},
                )
