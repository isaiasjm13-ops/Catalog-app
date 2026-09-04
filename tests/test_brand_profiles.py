from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from reportlab.pdfbase import pdfmetrics

from perfect_catalog.catalog_exports import (
    MINIMUM_CATALOG_FONT_SIZE,
    NATSUKI_BODY_BOLD_FONT,
    NATSUKI_BODY_FONT,
    NATSUKI_TITLE_FONT,
    _catalog_pdf_fonts,
    _register_natsuki_fonts,
)

from perfect_catalog.brand_profiles import normalize_profile_input


ROOT = Path(__file__).resolve().parents[1]


def valid_profile(**overrides: str) -> dict[str, str]:
    values = {
        "code": "pdm", "display_name": "PDM", "tagline": "Calidad verificada",
        "primary_color": "#c60012", "secondary_color": "#202327",
        "ink_color": "#16191d", "paper_color": "#ffffff",
        "public_base_url": "https://catalogo.example/pdm",
    }
    values.update(overrides)
    return values


class BrandProfileTests(unittest.TestCase):
    def test_profile_normalizes_code_and_colors(self) -> None:
        profile = normalize_profile_input(valid_profile())
        self.assertEqual(profile["code"], "PDM")
        self.assertEqual(profile["primary_color"], "#C60012")
        self.assertEqual(profile["paper_color"], "#FFFFFF")

    def test_profile_rejects_unsafe_url_and_invalid_colors(self) -> None:
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            normalize_profile_input(valid_profile(public_base_url="http://example.test"))
        with self.assertRaisesRegex(ValueError, "hexadecimal"):
            normalize_profile_input(valid_profile(primary_color="red"))
        with self.assertRaisesRegex(ValueError, "contraste"):
            normalize_profile_input(valid_profile(ink_color="#AAAAAA"))
        with self.assertRaisesRegex(ValueError, "contraste"):
            normalize_profile_input(valid_profile(primary_color="#FFFF00"))

    def test_migration_is_forward_only_and_permissions_are_minimal(self) -> None:
        sql = (ROOT / "db/migrations/0013_brand_profiles.sql").read_text(encoding="utf-8")
        self.assertTrue(sql.startswith("BEGIN;"))
        self.assertTrue(sql.rstrip().endswith("COMMIT;"))
        self.assertNotIn("DROP TABLE", sql.upper())
        self.assertNotIn("UPDATE, DELETE", sql.upper())
        self.assertIn("GRANT SELECT, INSERT", sql)
        self.assertIn("NATSUKI", sql)

    def test_operator_page_has_secure_creation_contract(self) -> None:
        template = (ROOT / "src/perfect_catalog/templates/operator_brands.html").read_text(encoding="utf-8")
        api = (ROOT / "src/perfect_catalog/operator_api.py").read_text(encoding="utf-8")
        self.assertIn('action="/operator/brands"', template)
        self.assertIn('name="csrf_token"', template)
        self.assertIn('name="confirm" value="yes"', template)
        self.assertIn('_same_origin(request)', api)
        self.assertNotIn('style="--profile', template)

    def test_natsuki_master_logo_is_valid_packaged_svg(self) -> None:
        logo = ROOT / "src/perfect_catalog/assets/brands/natsuki/logo.svg"
        self.assertEqual(ET.parse(logo).getroot().tag, "{http://www.w3.org/2000/svg}svg")
        packaging = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('"assets/brands/*/*.svg"', packaging)

    def test_natsuki_fonts_register_and_minimum_is_twelve_points(self) -> None:
        _register_natsuki_fonts()
        registered = set(pdfmetrics.getRegisteredFontNames())
        self.assertTrue({NATSUKI_TITLE_FONT, NATSUKI_BODY_FONT, NATSUKI_BODY_BOLD_FONT} <= registered)
        self.assertEqual(MINIMUM_CATALOG_FONT_SIZE, 12)
        packaging = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('"assets/brands/*/fonts/*.ttf"', packaging)
        self.assertIn('"assets/brands/*/fonts/*.txt"', packaging)

    def test_pdf_fonts_are_generic_except_for_natsukis_own_bundled_logo(self) -> None:
        generic = _catalog_pdf_fonts({})
        self.assertEqual(generic, ("Helvetica-Bold", "Helvetica", "Helvetica-Bold"))
        other_brand = _catalog_pdf_fonts({"visual_profile": {"logo_asset_key": "brands/pdm/logo.svg"}})
        self.assertEqual(other_brand, ("Helvetica-Bold", "Helvetica", "Helvetica-Bold"))
        natsuki = _catalog_pdf_fonts({"visual_profile": {"logo_asset_key": "brands/natsuki/logo.svg"}})
        self.assertEqual(natsuki, (NATSUKI_TITLE_FONT, NATSUKI_BODY_FONT, NATSUKI_BODY_BOLD_FONT))

    def test_brand_workflow_migration_binds_plan_brand_and_visual_contract(self) -> None:
        sql = (ROOT / "db/migrations/0014_brand_profile_workflow.sql").read_text(encoding="utf-8")
        self.assertTrue(sql.startswith("BEGIN;"))
        self.assertTrue(sql.rstrip().endswith("COMMIT;"))
        self.assertIn("brand_profile_id", sql)
        self.assertIn("minimum_font_size_pt", sql)
        self.assertIn("watermark_opacity", sql)
        self.assertIn("[.]svg$", sql)
        self.assertNotIn("\\\\.svg$", sql)
        self.assertNotIn("DROP ", sql.upper())
        template = (ROOT / "src/perfect_catalog/templates/operator_import_plan.html").read_text(encoding="utf-8")
        self.assertIn('Marca fijada en el dry-run', template)
        self.assertIn('plan.brand_profile_code', template)
        self.assertNotIn('name="brand_code"', template)

    def test_central_updater_applies_brand_prerequisites_once(self) -> None:
        bootstrap = (ROOT / "db/bootstrap/apply_pending_migrations.sql").read_text(encoding="utf-8")
        self.assertIn("to_regclass('perfect_catalog.brand_profile')", bootstrap)
        self.assertIn("\\ir ../migrations/0013_brand_profiles.sql", bootstrap)
        self.assertIn("information_schema.columns", bootstrap)
        self.assertIn("\\ir ../migrations/0014_brand_profile_workflow.sql", bootstrap)

    def test_brand_profiles_are_company_scoped(self) -> None:
        source = (ROOT / "src/perfect_catalog/brand_profiles.py").read_text(encoding="utf-8")
        self.assertIn("WHERE company_id=%s", source)
        self.assertIn("brand_profile_id, company_id, code", source)

    def test_plan_inspection_groups_joined_brand_profile(self) -> None:
        importer = (ROOT / "src/perfect_catalog/importer.py").read_text(encoding="utf-8")
        self.assertIn("GROUP BY p.import_plan_id, bp.brand_profile_id", importer)

    def test_link_brand_profile_validates_before_touching_the_database(self) -> None:
        from perfect_catalog.brand_profiles import link_brand_profile

        with self.assertRaisesRegex(ValueError, "operador"):
            link_brand_profile(
                brand_id="00000000-0000-0000-0000-000000000001",
                brand_profile_id="00000000-0000-0000-0000-000000000002",
                expected_previous_brand_profile_id=None,
                actor="", reason="Motivo suficientemente largo",
                config=None, password=None,
            )
        with self.assertRaisesRegex(ValueError, "motivo"):
            link_brand_profile(
                brand_id="00000000-0000-0000-0000-000000000001",
                brand_profile_id="00000000-0000-0000-0000-000000000002",
                expected_previous_brand_profile_id=None,
                actor="reviewer", reason="no",
                config=None, password=None,
            )

    def test_brand_profile_link_migration_is_append_only_and_scoped(self) -> None:
        sql = (ROOT / "db/migrations/0023_brand_profile_linking.sql").read_text(encoding="utf-8")
        self.assertTrue(sql.startswith("BEGIN;"))
        self.assertTrue(sql.rstrip().endswith("COMMIT;"))
        self.assertNotIn("DROP TABLE", sql.upper())
        self.assertIn("trg_brand_profile_link_event_append_only", sql)
        self.assertIn("ck_brand_profile_link_event_changes", sql)
        self.assertIn("GRANT UPDATE (brand_profile_id, updated_at) ON perfect_catalog.brand", sql)
        self.assertIn("GRANT SELECT, INSERT ON perfect_catalog.brand_profile_link_event", sql)

    def test_new_brand_form_defaults_to_neutral_colors_not_an_existing_brands(self) -> None:
        template = (ROOT / "src/perfect_catalog/templates/operator_brands.html").read_text(encoding="utf-8")
        add_brand_section = template.split('Añadir una marca')[1]
        self.assertNotIn("#C60012", add_brand_section)
        self.assertNotIn("#202327", add_brand_section)
        self.assertNotIn("#16191D", add_brand_section)
        self.assertIn('name="primary_color" value="#1F2937"', add_brand_section)

    def test_brands_page_offers_linking_form(self) -> None:
        template = (ROOT / "src/perfect_catalog/templates/operator_brands.html").read_text(encoding="utf-8")
        self.assertIn('action="/operator/brands/link"', template)
        self.assertIn('name="expected_previous_brand_profile_id"', template)


if __name__ == "__main__":
    unittest.main()
