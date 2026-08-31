from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from reportlab.pdfbase import pdfmetrics

from perfect_catalog.catalog_exports import (
    MINIMUM_CATALOG_FONT_SIZE,
    NATSUKI_BODY_BOLD_FONT,
    NATSUKI_BODY_FONT,
    NATSUKI_TITLE_FONT,
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
        self.assertIn('name="brand_code"', template)

    def test_central_updater_applies_brand_prerequisites_once(self) -> None:
        bootstrap = (ROOT / "db/bootstrap/apply_pending_migrations.sql").read_text(encoding="utf-8")
        self.assertIn("to_regclass('perfect_catalog.brand_profile')", bootstrap)
        self.assertIn("\\ir ../migrations/0013_brand_profiles.sql", bootstrap)
        self.assertIn("information_schema.columns", bootstrap)
        self.assertIn("\\ir ../migrations/0014_brand_profile_workflow.sql", bootstrap)

    def test_plan_inspection_groups_joined_brand_profile(self) -> None:
        importer = (ROOT / "src/perfect_catalog/importer.py").read_text(encoding="utf-8")
        self.assertIn("GROUP BY p.import_plan_id, bp.brand_profile_id", importer)


if __name__ == "__main__":
    unittest.main()
