from __future__ import annotations

import unittest
from pathlib import Path

from perfect_catalog.visual_identities import _validate_logo


ROOT = Path(__file__).resolve().parents[1]


class VisualIdentityTests(unittest.TestCase):
    def test_svg_logo_rejects_scripts_and_external_resources(self) -> None:
        clean = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><path d="M0 0h10v10z"/></svg>'
        self.assertEqual(_validate_logo("perfect.svg", clean), ("image/svg+xml", "svg"))
        with self.assertRaisesRegex(ValueError, "scripts"):
            _validate_logo("bad.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>')
        with self.assertRaisesRegex(ValueError, "recursos externos"):
            _validate_logo("external.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.test/logo.png"/></svg>')

    def test_visual_identity_migration_is_forward_only_and_minimal(self) -> None:
        sql = (ROOT / "db/migrations/0015_visual_identity_assets.sql").read_text(encoding="utf-8")
        self.assertTrue(sql.startswith("BEGIN;"))
        self.assertTrue(sql.rstrip().endswith("COMMIT;"))
        self.assertNotIn("DROP ", sql.upper())
        self.assertIn("GRANT SELECT, INSERT", sql)
        self.assertIn("scope IN ('company', 'brand')", sql)

    def test_vehicle_make_logo_migration_keeps_one_exact_identity_target(self) -> None:
        sql = (ROOT / "db/migrations/0016_vehicle_make_visual_identity.sql").read_text(encoding="utf-8")
        self.assertTrue(sql.startswith("BEGIN;"))
        self.assertTrue(sql.rstrip().endswith("COMMIT;"))
        self.assertIn("scope IN ('company', 'brand', 'vehicle_make')", sql)
        self.assertIn("REFERENCES perfect_catalog.vehicle_make", sql)
        self.assertIn("scope='vehicle_make' AND brand_profile_id IS NULL AND vehicle_make_id IS NOT NULL", sql)
        self.assertNotIn("ON DELETE CASCADE", sql)
