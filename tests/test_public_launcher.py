import unittest
from pathlib import Path


class PublicCatalogLauncherTests(unittest.TestCase):
    def test_published_launcher_prompts_secret_and_does_not_use_excel_pilot(self) -> None:
        root = Path(__file__).resolve().parents[1]
        launcher = (root / "INICIAR-CATALOGO-PUBLICADO.cmd").read_text(encoding="utf-8")
        self.assertIn("--prompt-password", launcher)
        self.assertIn("--brand NATSUKI", launcher)
        self.assertNotIn("--source-dir", launcher)
        self.assertNotIn("PGPASSWORD", launcher)


if __name__ == "__main__":
    unittest.main()
