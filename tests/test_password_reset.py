from pathlib import Path
import unittest


class PasswordResetScriptTests(unittest.TestCase):
    def test_reset_never_stores_password_in_project_files(self) -> None:
        root = Path(__file__).resolve().parents[1]
        sql = (root / "db/bootstrap/reset_application_password.sql").read_text(encoding="utf-8")
        script = (root / "db/bootstrap/reset_application_password.ps1").read_text(encoding="utf-8")
        launcher = (root / "RESTABLECER-CONTRASENA-REVISOR.cmd").read_text(encoding="utf-8")
        combined = "\n".join((sql, script, launcher)).lower()
        self.assertIn("\\password perfect_catalog_app", sql.lower())
        self.assertNotIn("pgpassword", combined)
        self.assertNotIn("alter role perfect_catalog_app password", combined)
        self.assertIn("-w", script.lower())


if __name__ == "__main__":
    unittest.main()
