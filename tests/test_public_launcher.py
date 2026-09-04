import unittest
from pathlib import Path


class PublicCatalogLauncherTests(unittest.TestCase):
    def test_root_launcher_delegates_to_the_brand_aware_powershell_script(self) -> None:
        root = Path(__file__).resolve().parents[1]
        launcher = (root / "INICIAR-CATALOGO-PUBLICADO.cmd").read_text(encoding="utf-8")
        self.assertIn("start_published_catalog.ps1", launcher)
        self.assertNotIn("--brand NATSUKI", launcher)
        self.assertNotIn("PGPASSWORD", launcher)

    def test_powershell_script_asks_which_brand_instead_of_a_fixed_one(self) -> None:
        root = Path(__file__).resolve().parents[1]
        script = (root / "db/bootstrap/start_published_catalog.ps1").read_text(encoding="utf-8")
        self.assertIn("-AsSecureString", script)
        self.assertIn("Read-Host 'Codigo de la marca a abrir'", script)
        self.assertIn("--prompt-password", script)
        self.assertNotIn("--brand NATSUKI", script)
        self.assertNotIn("--source-dir", script)
        self.assertIn("Remove-Item Env:PGPASSWORD", script)
        self.assertIn("status = 'published'", script)

    def test_api_no_longer_offers_the_excel_pilot_mode(self) -> None:
        root = Path(__file__).resolve().parents[1]
        api = (root / "src/perfect_catalog/api.py").read_text(encoding="utf-8")
        self.assertNotIn("--source-dir", api)
        self.assertNotIn('"--source"', api)
        self.assertNotIn("ExcelCatalogRepository", api)
        self.assertIn('parser.add_argument("--brand", required=True', api)


if __name__ == "__main__":
    unittest.main()
