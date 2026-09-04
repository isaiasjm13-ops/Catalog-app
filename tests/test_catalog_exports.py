import io
import json
import hashlib
import base64
import csv
import os
import tempfile
import unittest
from unittest import mock
import uuid
import zipfile
from pathlib import Path
from PIL import Image as PILImage

from perfect_catalog import catalog_exports as catalog_exports_module
from perfect_catalog.catalog_exports import (
    _contained_size, _optimized_raster, export_rows_from_release, generate_catalog_html,
    generate_catalog_pdf, generate_catalog_pptx, generate_indesign_datamerge_csv, group_values,
)
from perfect_catalog import catalog_export_job as catalog_export_job_module
from perfect_catalog.catalog_export_job import (
    browse_catalog_release,
    build_catalog_bundle,
    build_catalog_preview,
    create_operator_catalog_export,
    _replace_with_retry,
    _selection,
    estimate_adaptive_indesign_layout,
    estimate_indesign_layout,
    record_indesign_preflight,
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


def fixture_release_with_categories():
    brand_id = uuid.uuid4()
    specs = [
        ("NK-101", "Motor / Empaques", ["Toyota"]),
        ("NK-102", "Motor / Empaques", ["Honda"]),
        ("NK-201", "Frenos / Pastillas", ["Toyota", "Honda"]),
        ("NK-202", "Frenos / Pastillas", []),
        ("NK-301", "Suspensión / Amortiguadores", ["Mazda"]),
    ]
    items = []
    for order, (reference, category, vehicle_makes) in enumerate(specs, start=1):
        template_id = uuid.uuid4()
        data = {
            "product_template_id": str(template_id), "product_variant_id": None,
            "internal_reference_original": reference, "internal_reference_normalized": reference,
            "name_original": f"Producto {reference}", "name_normalized": f"PRODUCTO {reference}",
            "category_path": category, "brand": "Natsuki", "quantity_available": 0,
            "vehicle_makes": vehicle_makes,
        }
        items.append({
            "item_order": order, "product_template_id": template_id, "product_variant_id": None,
            "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION, "snapshot_data": data,
            "snapshot_sha256": product_snapshot_sha256(data),
        })
    definition = {"snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION, "release_hash_algorithm": RELEASE_HASH_ALGORITHM,
                  "source_kind": "applied_catalog", "item_count": len(items), "source_plan_id": str(uuid.uuid4()),
                  "source_import_batch_id": str(uuid.uuid4()), "source_plan_fingerprint_sha256": "a"*64,
                  "contract_version": "test-v1", "rules_version": "test-v1", "selection": {}}
    release = {"catalog_release_id": uuid.uuid4(), "brand_id": brand_id, "version": "synthetic-v1", "status": "published", "definition": definition}
    release["snapshot_sha256"] = release_snapshot_sha256(brand_id, release["version"], definition, items)
    return release, items


class GroupValuesTests(unittest.TestCase):
    """`group_values` es la única implementación de fan-out por marca vehicular; la comparten
    `_groups` (exportación digital/InDesign), `build_catalog_preview` y `browse_catalog_release`."""

    def test_vehicle_make_fans_out_a_multi_brand_product(self) -> None:
        row = {"vehicle_makes": ["Toyota", "Honda"]}
        self.assertEqual(group_values(row, "vehicle_make", empty_label="Sin categoría"), ["Toyota", "Honda"])

    def test_vehicle_make_falls_back_when_empty_or_missing(self) -> None:
        self.assertEqual(group_values({"vehicle_makes": []}, "vehicle_make", empty_label="x"), ["Sin marca vehicular"])
        self.assertEqual(group_values({}, "vehicle_make", empty_label="x"), ["Sin marca vehicular"])

    def test_other_fields_use_the_caller_supplied_empty_label(self) -> None:
        self.assertEqual(group_values({"category_path": "Motor"}, "category_path", empty_label="Sin categoría"), ["Motor"])
        self.assertEqual(group_values({}, "category_path", empty_label="Sin categoría"), ["Sin categoría"])
        self.assertEqual(group_values({}, "brand", empty_label="Sin subgrupo"), ["Sin subgrupo"])


class CatalogExportTests(unittest.TestCase):
    def test_contained_image_size_never_crops_distorts_or_upscales(self) -> None:
        self.assertEqual(_contained_size(2000, 500, 4, 3), (4, 1))
        self.assertEqual(_contained_size(500, 2000, 4, 3), (.75, 3))
        self.assertEqual(_contained_size(2, 1, 4, 3), (2, 1))
        with self.assertRaises(ValueError):
            _contained_size(0, 1, 4, 3)

    def test_display_raster_is_bounded_without_touching_approved_original(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "approved.png"
            PILImage.new("RGB", (2400, 600), "red").save(source)
            original = source.read_bytes()
            optimized = _optimized_raster(source, 600, 600)
            with PILImage.open(optimized) as result:
                self.assertEqual(result.size, (600, 150))
                self.assertEqual(result.format, "JPEG")
            self.assertEqual(source.read_bytes(), original)

    def test_indesign_layout_estimate_matches_cover_separators_and_profile_capacity(self) -> None:
        estimate = estimate_indesign_layout(
            [{"count": 5}, {"count": 17}], "T4"
        )
        self.assertEqual(estimate["cover_pages"], 1)
        self.assertEqual(estimate["contents_pages"], 1)
        self.assertEqual(estimate["separator_pages"], 2)
        self.assertEqual(estimate["product_pages"], 7)
        self.assertEqual(estimate["estimated_page_count"], 11)
        self.assertEqual(estimate_indesign_layout([{"count": 17}], "TABLE")["estimated_page_count"], 5)
        with self.assertRaisesRegex(ValueError, "Perfil InDesign"):
            estimate_indesign_layout([{"count": 1}], "T8")

    def test_adaptive_indesign_layout_promotes_long_products_and_matches_groups(self) -> None:
        products = [
            {"category_path": "Motor", "name_original": "Breve", "applications": ["Toyota"]},
            {"category_path": "Motor", "name_original": "Largo", "applications": ["A" * 150]},
            {"category_path": "Motor", "name_original": "Muy largo", "applications": ["B" * 300]},
            {"category_path": "Frenos", "name_original": "Breve", "applications": ["Nissan"]},
        ]
        estimate = estimate_adaptive_indesign_layout(products, {"group_by": "category_path"}, "T4")
        self.assertEqual(estimate["separator_pages"], 2)
        self.assertEqual(estimate["product_pages"], 4)
        self.assertEqual(estimate["contents_pages"], 1)
        self.assertEqual(estimate["estimated_page_count"], 8)

    def test_indesign_preflight_is_bound_to_verified_export_and_stored_separately(self) -> None:
        release, items = fixture_release()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            export_id = uuid.uuid4()
            result = build_catalog_bundle(
                release, items, root / str(release["catalog_release_id"]) / str(export_id),
                formats=("indesign-json",), config={"template_profile": "T4", "theme": "forest"},
            )
            report = {
                "schema": "perfect-catalog.indesign-preflight.v1",
                "release_id": str(release["catalog_release_id"]),
                "snapshot_sha256": release["snapshot_sha256"], "template_profile": "T4",
                "theme": "forest", "product_count": 1, "linked_image_count": 0,
                "missing_images": [{"product_index": 0, "reference": "NK-001", "reason": "ausente"}],
                "overflow_product_indexes": [], "unavailable_fonts": [],
                "group_count": 1, "page_count": 4,
            }
            receipt = record_indesign_preflight(
                root, release["catalog_release_id"], export_id,
                json.dumps(report).encode(), actor="qa", reason="Preflight ejecutado en InDesign",
            )
            self.assertEqual(receipt["schema"], "perfect-catalog.indesign-preflight-receipt.v1")
            self.assertEqual(receipt["quality"]["status"], "issues")
            self.assertEqual(receipt["quality"]["expected_layout"]["estimated_page_count"], 4)
            self.assertTrue(Path(receipt["path"]).is_file())
            self.assertNotIn("_indesign_preflight", {path.name for path in (root / str(release["catalog_release_id"]) / str(export_id)).iterdir()})
            report["theme"] = "classic"
            with self.assertRaisesRegex(ValueError, "no coincide"):
                record_indesign_preflight(
                    root, release["catalog_release_id"], export_id,
                    json.dumps(report).encode(), actor="qa", reason="Tema incorrecto",
                )
            report["theme"] = "forest"
            report["page_count"] = 5
            with self.assertRaisesRegex(ValueError, "paginación.*no coincide"):
                record_indesign_preflight(
                    root, release["catalog_release_id"], export_id,
                    json.dumps(report).encode(), actor="qa", reason="Páginas incorrectas",
                )
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
        self.assertNotIn("quantity_available", rows[0])
        release["snapshot_sha256"] = "0"*64
        with self.assertRaisesRegex(ValueError, "snapshot_sha256"):
            export_rows_from_release(release, items)

    def test_manual_reference_selection_preserves_editorial_order(self) -> None:
        rows = [
            {"internal_reference_original": "A", "category_path": "Motor"},
            {"internal_reference_original": "B", "category_path": "Motor"},
            {"internal_reference_original": "C", "category_path": "Motor"},
        ]
        selected, evidence = _selection(rows, {"selected_references": "C\nA"})
        self.assertEqual([row["internal_reference_original"] for row in selected], ["C", "A"])
        self.assertEqual(evidence["selected_references"], ["C", "A"])

    def test_generated_pdf_and_pptx_are_valid_containers_with_content(self) -> None:
        release, items = fixture_release()
        rows = export_rows_from_release(release, items)
        config = {
            "title": "Catálogo sintético", "columns_per_row": 3, "theme": "industrial",
            "visual_profile": {"company": {"display_name": "PDM"}},
        }
        pdf = generate_catalog_pdf(
            rows, config,
            release=release,
        )
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertIn(b"%%EOF", pdf[-64:])
        self.assertGreaterEqual(pdf.count(b"/Type /Page"), 3)
        self.assertIn(b"/Author (PDM)", pdf)
        self.assertNotIn(b"Perfect Trading", pdf)
        self.assertIn(b"/Title (Cat", pdf)
        pptx = generate_catalog_pptx(
            rows, config,
            release=release,
        )
        self.assertTrue(pptx.startswith(b"PK"))
        with zipfile.ZipFile(io.BytesIO(pptx)) as archive:
            slides = [name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")]
            slide_xml = "".join(archive.read(name).decode("utf-8") for name in slides)
        self.assertGreaterEqual(len(slides), 2)
        self.assertIn("E30613", slide_xml)
        self.assertIn(">PDM<", slide_xml)
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
        rows[0]["oem_references"] = ["OEM-123"]
        rows[0]["fmsi_references"] = ["D1035-7779"]
        rows[0]["additional_references"] = ["ALT-99"]
        rows[0]["applications"] = ["Toyota Hilux"]
        rows[0]["vehicle_makes"] = ["Toyota"]
        content = generate_catalog_html(
            rows, {"title": "Edición digital", "columns_per_row": 3, "theme": "industrial"}, release=release
        ).decode("utf-8")
        self.assertTrue(content.startswith("<!doctype html>"))
        self.assertIn("@media(max-width:760px)", content)
        self.assertIn(str(release["snapshot_sha256"]), content)
        self.assertIn('src="image-safe.png"', content)
        self.assertIn('loading="lazy" decoding="async"', content)
        self.assertIn(".photo img{display:block;width:100%;height:100%;object-fit:contain;object-position:center center}", content)
        self.assertIn('<button class="photo" type="button"', content)
        self.assertIn('<dialog class="photo-viewer" id="photo-viewer">', content)
        self.assertIn("photo-viewer-details", content)
        self.assertIn("Ver ficha completa", content)
        self.assertIn("node.cloneNode(true)", content)
        self.assertIn(".photo-viewer img{grid-column:1/-1;width:100%;height:100%;min-height:0;object-fit:contain", content)
        self.assertIn("viewerImage.src=source.currentSrc||source.src", content)
        self.assertIn("--forest:#C34A21", content)
        self.assertIn('role="search"', content)
        self.assertIn('id="catalog-query" type="search" inputmode="search"', content)
        self.assertIn("card.dataset.search.includes(term)", content)
        self.assertIn("terms.every(term=>card.dataset.search.includes(term)", content)
        self.assertIn("card.dataset.searchCompact.includes(compact(term))", content)
        self.assertIn("data-search=", content)
        self.assertIn("normalize('NFD')", content)
        self.assertIn('class="catalog-filter-panel"', content)
        self.assertIn('id="filter-category"', content)
        self.assertIn('id="filter-brand"', content)
        self.assertIn('id="filter-vehicle"', content)
        self.assertIn('<option value="Toyota">Toyota</option>', content)
        self.assertIn('id="view-list"', content)
        self.assertIn("catalog-list-view", content)
        self.assertIn("localStorage.setItem(stateKey", content)
        self.assertIn("scrollY:window.scrollY", content)
        self.assertIn('data-category="Motor / Empaques"', content)
        self.assertIn('data-brand="Natsuki"', content)
        self.assertIn('data-vehicle="Toyota"', content)
        self.assertNotIn("fetch(", content)
        self.assertIn("Motor / Empaques · Natsuki", content)
        self.assertIn("<dt>OEM</dt><dd>OEM-123</dd>", content)
        self.assertIn("<dt>FMSI</dt><dd>D1035-7779</dd>", content)
        self.assertIn("<dt>Alternas</dt><dd>ALT-99</dd>", content)
        self.assertIn("<dt>Aplicaciones</dt><dd>Toyota Hilux</dd>", content)

    def test_digital_search_indexes_hidden_codes_and_technical_fields(self) -> None:
        release, items = fixture_release()
        rows = export_rows_from_release(release, items)
        rows[0].update({
            "internal_reference_normalized": "NK-001",
            "applications": ["Toyota Hilux 2012"],
            "engine_types": ["1KD FTV"],
            "oem_references": ["44310-0K020"],
            "additional_references": ["ABC 99-XY"],
        })
        content = generate_catalog_html(
            rows,
            {"show_applications": False, "show_engine": False, "show_oem": False},
            release=release,
        ).decode("utf-8")
        article = content.split('<article class="product"', 1)[1].split(">", 1)[0]
        self.assertIn("Toyota Hilux 2012", article)
        self.assertIn("1KD FTV", article)
        self.assertIn("44310-0K020", article)
        self.assertIn("ABC 99-XY", article)
        self.assertNotIn("<dt>Aplicaciones</dt>", content)

    def test_standalone_html_embeds_approved_image_as_data_uri(self) -> None:
        release, items = fixture_release()
        rows = export_rows_from_release(release, items)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            PILImage.new("RGB", (1600, 400), "red").save(root / "approved.png")
            rows[0].update({
                "image_path": "approved.png", "image_media_type": "image/png",
            })
            content = generate_catalog_html(
                rows, release=release, bundle_dir=root, embed_images=True,
            ).decode("utf-8")
        self.assertIn("data:image/jpeg;base64,", content)
        self.assertEqual(content.count("data:image/jpeg;base64,"), 1)
        self.assertNotIn('src="approved.png"', content)
        encoded = content.split("data:image/jpeg;base64,", 1)[1].split('"', 1)[0]
        with PILImage.open(io.BytesIO(base64.b64decode(encoded))) as embedded:
            self.assertEqual(embedded.size, (1200, 300))
        self.assertNotIn("data-gallery=", content)

    def test_digital_html_gallery_lists_variant_photo_filenames_alongside_the_main_one(self) -> None:
        release, items = fixture_release()
        rows = export_rows_from_release(release, items)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("approved.png", "variant2.png", "variant3.png"):
                PILImage.new("RGB", (400, 300), "red").save(root / name)
            rows[0].update({
                "image_path": "approved.png",
                "variant_image_paths": ["variant2.png", "variant3.png"],
            })
            content = generate_catalog_html(rows, release=release, bundle_dir=root).decode("utf-8")
        self.assertIn('data-gallery="approved.png|variant2.png|variant3.png"', content)
        self.assertIn('src="approved.png"', content)
        self.assertIn('3 fotos', content)
        self.assertIn("photo-viewer-gallery", content)
        self.assertIn("photo-viewer-thumb", content)

    def test_standalone_html_embeds_every_variant_photo_as_its_own_data_uri(self) -> None:
        release, items = fixture_release()
        rows = export_rows_from_release(release, items)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            PILImage.new("RGB", (400, 300), "red").save(root / "approved.png")
            PILImage.new("RGB", (400, 300), "blue").save(root / "variant2.png")
            rows[0].update({
                "image_path": "approved.png", "variant_image_paths": ["variant2.png"],
            })
            content = generate_catalog_html(
                rows, release=release, bundle_dir=root, embed_images=True,
            ).decode("utf-8")
        self.assertEqual(content.count("data:image/jpeg;base64,"), 3)
        gallery_attr = content.split('data-gallery="', 1)[1].split('"', 1)[0]
        sources = gallery_attr.split("|")
        self.assertEqual(len(sources), 2)
        self.assertNotEqual(sources[0], sources[1])

    def test_visual_profile_overrides_palette_embeds_brand_and_minimum_type(self) -> None:
        release, items = fixture_release()
        rows = export_rows_from_release(release, items)
        rows[0].update({"applications": ["Toyota Corolla 2014"], "engine_types": ["1.8L"], "oem_references": ["OEM-123"]})
        visual = {"primary_color": "#E30613", "secondary_color": "#12355B", "ink_color": "#111111", "paper_color": "#FFFFFF", "logo_asset_key": "brands/natsuki/logo.svg", "corner_logo_enabled": True, "watermark_enabled": True, "watermark_opacity": .05, "company": {"display_name": "Perfect Demo", "primary_color": "#086650", "secondary_color": "#C7DF54", "ink_color": "#17211D", "paper_color": "#FFFFFF"}}
        html = generate_catalog_html(rows, {"template_profile": "T4", "visual_profile": visual}).decode("utf-8")
        self.assertIn("--forest:#E30613", html)
        self.assertIn("--secondary:#12355B", html)
        self.assertIn("--company-primary:#086650", html)
        self.assertIn("--company-secondary:#C7DF54", html)
        self.assertIn("corporate-signature", html)
        self.assertIn("Perfect Demo", html)
        self.assertIn("font-size:16px", html)
        self.assertIn("class=\"brand-logo\"", html)
        self.assertIn("data:image/png;base64,", html)
        self.assertIn('class="contents" aria-label="Secciones del catálogo"', html)
        self.assertIn('id="seccion-01"', html)
        self.assertIn("Motor / Empaques", html)
        self.assertIn("Toyota Corolla 2014", html)
        self.assertIn("OEM-123", html)
        compact = generate_catalog_html(rows, {"visual_profile": visual, "show_brand": False, "show_oem": False, "show_engine": False}).decode("utf-8")
        self.assertNotIn("<dt>OEM</dt>", compact)
        self.assertNotIn("<dt>Motor</dt>", compact)
        self.assertNotIn("Motor / Empaques · Natsuki", compact)
        self.assertTrue(generate_catalog_pdf(rows, {"template_profile": "T1", "visual_profile": visual}).startswith(b"%PDF-"))
        pptx = generate_catalog_pptx(rows, {"template_profile": "T1", "visual_profile": visual})
        with zipfile.ZipFile(io.BytesIO(pptx)) as presentation:
            slide_xml = b"".join(presentation.read(name) for name in presentation.namelist() if name.startswith("ppt/slides/slide"))
        self.assertIn(b"12355B", slide_xml)
        self.assertIn(b"086650", slide_xml)
        self.assertIn(b"Perfect Demo", slide_xml)

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
        image_buffer = io.BytesIO()
        PILImage.new("RGB", (120, 60), "blue").save(image_buffer, format="JPEG")
        content = image_buffer.getvalue()
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
                release, items, output,
                formats=("html", "html-standalone", "indesign-json"),
                image_root=root / "images",
            )
            image_entry = next(entry for entry in result["files"] if entry["format"] == "image")
            self.assertEqual((output / image_entry["filename"]).read_bytes(), content)
            snapshot_entry = next(entry for entry in result["files"] if entry["format"] == "indesign-json")
            snapshot = json.loads((output / snapshot_entry["filename"]).read_text(encoding="utf-8"))
            self.assertEqual(snapshot["products"][0]["image_path"], image_entry["filename"])
            standalone = next(entry for entry in result["files"] if entry["format"] == "html-standalone")
            standalone_text = (output / standalone["filename"]).read_text(encoding="utf-8")
            self.assertIn("data:image/jpeg;base64,", standalone_text)
            self.assertNotIn(f'src="{image_entry["filename"]}"', standalone_text)
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

    def test_bundle_packages_variant_photos_alongside_the_main_one(self) -> None:
        release, items = fixture_release()
        primary_bytes = io.BytesIO()
        PILImage.new("RGB", (120, 60), "blue").save(primary_bytes, format="JPEG")
        primary_content = primary_bytes.getvalue()
        primary_digest = hashlib.sha256(primary_content).hexdigest()
        variant_bytes = io.BytesIO()
        PILImage.new("RGB", (120, 60), "green").save(variant_bytes, format="JPEG")
        variant_content = variant_bytes.getvalue()
        variant_digest = hashlib.sha256(variant_content).hexdigest()
        data = items[0]["snapshot_data"]
        data.update({
            "image_status": True,
            "image_storage_relpath": f"objects/{primary_digest[:2]}/{primary_digest}.jpg",
            "image_sha256": primary_digest, "image_media_type": "image/jpeg",
            "variant_images": [{
                "storage_relpath": f"objects/{variant_digest[:2]}/{variant_digest}.jpg",
                "sha256": variant_digest, "media_type": "image/jpeg", "variant_index": 2,
            }],
        })
        items[0]["snapshot_sha256"] = product_snapshot_sha256(data)
        release["snapshot_sha256"] = release_snapshot_sha256(
            release["brand_id"], release["version"], release["definition"], items
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            primary_source = root / "images" / data["image_storage_relpath"]
            primary_source.parent.mkdir(parents=True)
            primary_source.write_bytes(primary_content)
            variant_source = root / "images" / data["variant_images"][0]["storage_relpath"]
            variant_source.parent.mkdir(parents=True, exist_ok=True)
            variant_source.write_bytes(variant_content)
            output = root / "bundle"
            result = build_catalog_bundle(
                release, items, output, formats=("html", "html-standalone"), image_root=root / "images",
            )
            image_entries = [entry for entry in result["files"] if entry["format"] == "image"]
            self.assertEqual({entry["sha256"] for entry in image_entries}, {primary_digest, variant_digest})
            html_entry = next(entry for entry in result["files"] if entry["format"] == "html")
            html_text = (output / html_entry["filename"]).read_text(encoding="utf-8")
            self.assertIn(f"image-{primary_digest}.jpg|image-{variant_digest}.jpg", html_text)
            standalone_entry = next(entry for entry in result["files"] if entry["format"] == "html-standalone")
            standalone_text = (output / standalone_entry["filename"]).read_text(encoding="utf-8")
            self.assertEqual(standalone_text.count("data:image/jpeg;base64,"), 3)

    def test_standalone_html_refuses_to_embed_photos_over_the_size_cap(self) -> None:
        release, items = fixture_release()
        image_buffer = io.BytesIO()
        PILImage.new("RGB", (120, 60), "blue").save(image_buffer, format="JPEG")
        content = image_buffer.getvalue()
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
            with mock.patch("perfect_catalog.catalog_export_job.MAX_STANDALONE_EMBED_IMAGE_BYTES", 10):
                with self.assertRaisesRegex(ValueError, "ZIP digital"):
                    build_catalog_bundle(
                        release, items, root / "bundle",
                        formats=("html-standalone",), image_root=root / "images",
                    )
            result = build_catalog_bundle(
                release, items, root / "under-cap",
                formats=("html-standalone",), image_root=root / "images",
            )
            self.assertEqual([entry["format"] for entry in result["files"]], ["image", "html-standalone"])

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

    def test_optimized_raster_reuses_cached_bytes_for_the_same_size_and_quality(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "photo.png"
            PILImage.new("RGB", (400, 300), "blue").save(path)
            cache: dict = {}
            with mock.patch("perfect_catalog.catalog_exports.PILImage.open", wraps=PILImage.open) as opened:
                first = _optimized_raster(path, 200, 150, cache=cache)
                second = _optimized_raster(path, 200, 150, cache=cache)
            self.assertEqual(opened.call_count, 1)
            self.assertEqual(first.getvalue(), second.getvalue())
            with mock.patch("perfect_catalog.catalog_exports.PILImage.open", wraps=PILImage.open) as opened_different_size:
                _optimized_raster(path, 100, 100, cache=cache)
            self.assertEqual(opened_different_size.call_count, 1)
            with mock.patch("perfect_catalog.catalog_exports.PILImage.open", wraps=PILImage.open) as opened_no_cache:
                _optimized_raster(path, 200, 150)
                _optimized_raster(path, 200, 150)
            self.assertEqual(opened_no_cache.call_count, 2)

    def test_shared_product_photo_is_only_decoded_once_per_export(self) -> None:
        image = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
        rows = [
            {"internal_reference_original": f"IMG-00{index}", "name_original": "Producto visual",
             "category_path": "Visual", "image_path": "shared.png"}
            for index in (1, 2, 3)
        ]
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary)
            (bundle / "shared.png").write_bytes(image)
            with mock.patch(
                "perfect_catalog.catalog_exports._optimized_raster", wraps=catalog_exports_module._optimized_raster,
            ) as raster:
                self.assertTrue(generate_catalog_pdf(rows, bundle_dir=bundle).startswith(b"%PDF-"))
                self.assertEqual(raster.call_count, 3)
                cache_used = [call.kwargs.get("cache") for call in raster.call_args_list]
                self.assertTrue(all(cache is cache_used[0] and cache is not None for cache in cache_used))

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
            (output / filename).write_bytes(b"alterado")
            with self.assertRaisesRegex(ValueError, "no coincide"):
                resolve_catalog_download(root, release["catalog_release_id"], export_id, filename)
            with self.assertRaises(PermissionError):
                resolve_catalog_download(root, release["catalog_release_id"], export_id, "private.txt")
            with self.assertRaises(ValueError):
                resolve_catalog_download(root, release["catalog_release_id"], export_id, "../private.txt")

    def test_history_orders_by_real_export_time_not_by_random_uuid(self) -> None:
        """`export_id`/`release_id` son UUID aleatorios: ordenar por su texto no refleja
        cuál exportación es más reciente. El orden debe salir de la fecha real del manifiesto."""
        release, items = fixture_release()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            older_id = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
            newer_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
            older_output = root / str(release["catalog_release_id"]) / str(older_id)
            newer_output = root / str(release["catalog_release_id"]) / str(newer_id)
            build_catalog_bundle(release, items, older_output, formats=("indesign-json",))
            older_manifest = next(older_output.glob("*.manifest.json"))
            os.utime(older_manifest, (1_000_000, 1_000_000))
            build_catalog_bundle(release, items, newer_output, formats=("indesign-json",))
            newer_manifest = next(newer_output.glob("*.manifest.json"))
            os.utime(newer_manifest, (2_000_000, 2_000_000))
            history = list_operator_catalog_exports(root)
            self.assertEqual([entry["export_id"] for entry in history], [str(newer_id), str(older_id)])

    def test_real_operator_exports_are_indexed_incrementally_not_rewalked(self) -> None:
        """`create_operator_catalog_export` (el camino real de la consola) debe anexar al
        índice en vez de dejar que el próximo listado recorra todo el disco otra vez."""
        release, items = fixture_release()
        image = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
        digest = hashlib.sha256(image).hexdigest()
        data = items[0]["snapshot_data"]
        data.update({
            "image_status": True, "image_storage_relpath": f"objects/{digest[:2]}/{digest}.png",
            "image_sha256": digest, "image_media_type": "image/png",
        })
        items[0]["snapshot_sha256"] = product_snapshot_sha256(data)
        release["snapshot_sha256"] = release_snapshot_sha256(
            release["brand_id"], release["version"], release["definition"], items
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image_root = root / "images"
            image_path = image_root / data["image_storage_relpath"]
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(image)
            with mock.patch.object(catalog_export_job_module, "load_published_release", return_value=(release, items)):
                first = create_operator_catalog_export(
                    release["catalog_release_id"], mock.MagicMock(), "secret", root / "exports",
                    formats=("indesign-json",), config={}, image_root=image_root,
                )
                index_path = root / "exports" / catalog_export_job_module.EXPORT_INDEX_FILENAME
                self.assertTrue(index_path.is_file())
                self.assertEqual(len(index_path.read_text(encoding="utf-8").splitlines()), 1)
                second = create_operator_catalog_export(
                    release["catalog_release_id"], mock.MagicMock(), "secret", root / "exports",
                    formats=("indesign-json",), config={}, image_root=image_root,
                )
            self.assertEqual(len(index_path.read_text(encoding="utf-8").splitlines()), 2)
            with mock.patch.object(catalog_export_job_module, "_rebuild_export_index") as rebuild:
                history = list_operator_catalog_exports(root / "exports")
            rebuild.assert_not_called()
            self.assertEqual(
                [entry["export_id"] for entry in history],
                [second["export_id"], first["export_id"]],
            )

    def test_preview_revalidates_release_and_limits_rendered_products(self) -> None:
        release, items = fixture_release()
        preview = build_catalog_preview(release, items, group_by="category_path", sample_limit=1)
        self.assertEqual(preview["total_count"], 1)
        self.assertEqual(preview["sample_count"], 1)
        self.assertEqual(preview["groups"][0]["count"], 1)
        release["snapshot_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "snapshot_sha256"):
            build_catalog_preview(release, items)

    def test_preview_uses_the_same_exact_reference_selection_as_export(self) -> None:
        release, items = fixture_release()
        preview = build_catalog_preview(
            release, items, selected_references="nk-001\nNK-001", sample_limit=24
        )
        self.assertEqual(preview["total_count"], 1)
        self.assertEqual(preview["selected_references"], ["nk-001"])
        self.assertRegex(preview["selected_references_sha256"], r"^[0-9a-f]{64}$")
        with self.assertRaisesRegex(ValueError, "Referencias no encontradas"):
            build_catalog_preview(release, items, selected_references="NO-EXISTE")

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

    def test_vehicle_make_can_group_products_into_each_application_brand(self) -> None:
        rows = [{
            "internal_reference_original": "A-1", "name_original": "Producto",
            "vehicle_makes": ["Toyota", "Nissan"], "applications": ["Toyota Corolla", "Nissan Sentra"],
        }]
        from perfect_catalog.catalog_exports import _groups
        groups = _groups(rows, "vehicle_make")
        self.assertEqual([label for label, _ in groups], ["Toyota", "Nissan"])

    def test_vehicle_make_logo_appears_only_beside_vehicle_group_heading(self) -> None:
        rows = [{
            "internal_reference_original": "A-1", "name_original": "Producto",
            "vehicle_makes": ["Toyota"], "applications": ["Toyota Corolla"],
        }]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "vehicle-logo.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><path d="M0 0h10v10z"/></svg>',
                encoding="utf-8",
            )
            config = {"group_by": "vehicle_make", "visual_profile": {"vehicle_makes": {
                "Toyota": {"packaged_logo_path": "vehicle-logo.svg"},
            }}}
            html = generate_catalog_html(rows, config, bundle_dir=root).decode("utf-8")
            standalone = generate_catalog_html(
                rows, config, bundle_dir=root, embed_images=True,
            ).decode("utf-8")
        self.assertIn('class="vehicle-make-logo" src="vehicle-logo.svg" alt="Logo de Toyota"', html)
        self.assertIn('class="vehicle-make-logo" src="data:image/svg+xml;base64,', standalone)
        self.assertEqual(html.count('class="vehicle-make-logo"'), 1)

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

    def test_digital_html_offers_copy_reference_button_with_clipboard_fallback(self) -> None:
        release, items = fixture_release()
        rows = export_rows_from_release(release, items)
        content = generate_catalog_html(rows, {"title": "Edición digital"}, release=release).decode("utf-8")
        self.assertIn('<button class="ref-copy" type="button" data-ref="NK-001">', content)
        self.assertIn('<code>NK-001</code><span class="copy-hint" aria-hidden="true">Copiar</span>', content)
        self.assertIn("navigator.clipboard&&navigator.clipboard.writeText", content)
        self.assertIn("document.execCommand('copy')", content)
        self.assertNotIn("wa.me", content)

    def test_export_finalization_retries_transient_windows_permission_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            target = root / "target"
            attempts = {"count": 0}
            real_replace = Path.replace

            def flaky_replace(self, destination):
                attempts["count"] += 1
                if attempts["count"] < 3:
                    raise PermissionError(5, "Acceso denegado")
                return real_replace(self, destination)

            with mock.patch("perfect_catalog.catalog_export_job.time.sleep"), \
                 mock.patch.object(Path, "replace", flaky_replace):
                _replace_with_retry(source, target)
            self.assertEqual(attempts["count"], 3)
            self.assertTrue(target.is_dir())

    def test_export_finalization_reraises_after_exhausting_retries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            target = root / "target"

            def always_denied(self, destination):
                raise PermissionError(5, "Acceso denegado")

            with mock.patch("perfect_catalog.catalog_export_job.time.sleep"), \
                 mock.patch.object(Path, "replace", always_denied):
                with self.assertRaises(PermissionError):
                    _replace_with_retry(source, target, attempts=3)


class BrowseCatalogReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        catalog_export_job_module._EXPORT_ROWS_CACHE.clear()

    def _mock_load(self, release, items):
        return mock.patch.object(
            catalog_export_job_module, "load_published_release", return_value=(release, items),
        )

    def test_defaults_to_the_first_category_alphabetically_with_pagination(self) -> None:
        release, items = fixture_release_with_categories()
        with self._mock_load(release, items):
            result = browse_catalog_release(release["catalog_release_id"], mock.MagicMock(), "secret")
            self.assertEqual(result["group_by"], "category_path")
            self.assertEqual(
                [group["label"] for group in result["groups"]],
                ["Frenos / Pastillas", "Motor / Empaques", "Suspensión / Amortiguadores"],
            )
            self.assertEqual(result["active_group"], "Frenos / Pastillas")
            self.assertEqual(result["group_count"], 2)
            self.assertEqual(result["total_count"], 5)
            self.assertEqual(result["total_pages"], 1)
            self.assertEqual(
                [product["internal_reference_original"] for product in result["products"]],
                ["NK-201", "NK-202"],
            )

            paged = browse_catalog_release(
                release["catalog_release_id"], mock.MagicMock(), "secret",
                group="Frenos / Pastillas", page=2, page_size=1,
            )
            self.assertEqual(paged["total_pages"], 2)
            self.assertEqual(paged["page"], 2)
            self.assertEqual(
                [product["internal_reference_original"] for product in paged["products"]], ["NK-202"],
            )

    def test_vehicle_make_grouping_fans_out_multi_brand_products(self) -> None:
        release, items = fixture_release_with_categories()
        with self._mock_load(release, items):
            result = browse_catalog_release(
                release["catalog_release_id"], mock.MagicMock(), "secret",
                group_by="vehicle_make", group="Toyota",
            )
            self.assertEqual(
                sorted(product["internal_reference_original"] for product in result["products"]),
                ["NK-101", "NK-201"],
            )
            unassigned = browse_catalog_release(
                release["catalog_release_id"], mock.MagicMock(), "secret",
                group_by="vehicle_make", group="Sin marca vehicular",
            )
            self.assertEqual(
                [product["internal_reference_original"] for product in unassigned["products"]], ["NK-202"],
            )

    def test_rejects_unknown_grouping_and_out_of_range_pagination(self) -> None:
        release, items = fixture_release_with_categories()
        with self._mock_load(release, items):
            with self.assertRaisesRegex(ValueError, "Agrupación"):
                browse_catalog_release(release["catalog_release_id"], mock.MagicMock(), "secret", group_by="brand")
            with self.assertRaisesRegex(ValueError, "page"):
                browse_catalog_release(release["catalog_release_id"], mock.MagicMock(), "secret", page=0)
            with self.assertRaisesRegex(ValueError, "page_size"):
                browse_catalog_release(release["catalog_release_id"], mock.MagicMock(), "secret", page_size=1000)

    def test_repeated_browsing_does_not_reverify_the_release_every_call(self) -> None:
        release, items = fixture_release_with_categories()
        with self._mock_load(release, items), mock.patch.object(
            catalog_export_job_module, "export_rows_from_release", wraps=catalog_export_job_module.export_rows_from_release,
        ) as export_rows:
            browse_catalog_release(release["catalog_release_id"], mock.MagicMock(), "secret", group="Motor / Empaques")
            browse_catalog_release(release["catalog_release_id"], mock.MagicMock(), "secret", group="Suspensión / Amortiguadores")
            browse_catalog_release(release["catalog_release_id"], mock.MagicMock(), "secret", group_by="vehicle_make", group="Mazda")
        export_rows.assert_called_once()
