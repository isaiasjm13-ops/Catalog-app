from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CompanyBrandAssignmentAuditTests(unittest.TestCase):
    def test_launcher_uses_hidden_password_and_saves_a_report(self) -> None:
        script = (ROOT / "db/bootstrap/audit_company_brand_assignment.ps1").read_text(encoding="utf-8")
        self.assertIn("Read-Host 'Contrasena de PostgreSQL para postgres' -AsSecureString", script)
        self.assertIn("audit_company_brand_assignment.sql", script)
        self.assertIn("Remove-Item Env:PGPASSWORD", script)
        self.assertIn("Tee-Object -FilePath $reportPath", script)
        self.assertNotIn("DROP ", script.upper())

    def test_audit_sql_is_strictly_read_only(self) -> None:
        sql = (ROOT / "db/validation/audit_company_brand_assignment.sql").read_text(encoding="utf-8")
        for forbidden in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ", "TRUNCATE "):
            self.assertNotIn(forbidden, sql.upper())
        for evidence in ("perfect_catalog.company", "perfect_catalog.brand", "company_admin_event"):
            self.assertIn(evidence, sql)

    def test_root_launcher_delegates_to_the_powershell_script(self) -> None:
        launcher = (ROOT / "AUDITAR-EMPRESAS-MARCAS.cmd").read_text(encoding="utf-8")
        self.assertIn("audit_company_brand_assignment.ps1", launcher)


if __name__ == "__main__":
    unittest.main()
