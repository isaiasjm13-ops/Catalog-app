from pathlib import Path
import unittest

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


if __name__ == "__main__":
    unittest.main()
