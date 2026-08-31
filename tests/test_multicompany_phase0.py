from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MultiCompanyPhaseZeroTests(unittest.TestCase):
    def test_launcher_uses_hidden_password_backup_verification_and_read_only_audit(self) -> None:
        script = (ROOT / "db/bootstrap/prepare_multicompany_phase0.ps1").read_text(encoding="utf-8")
        self.assertIn("Read-Host 'Contraseña de PostgreSQL para postgres' -AsSecureString", script)
        self.assertIn("--format=custom", script)
        self.assertIn("--list $backupFile", script)
        self.assertIn("audit_pre_multicompany.sql", script)
        self.assertIn("Remove-Item Env:PGPASSWORD", script)
        self.assertNotIn("DROP ", script.upper())

    def test_audit_sql_is_read_only_and_covers_required_evidence(self) -> None:
        sql = (ROOT / "db/validation/audit_pre_multicompany.sql").read_text(encoding="utf-8")
        for forbidden in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ", "TRUNCATE "):
            self.assertNotIn(forbidden, sql.upper())
        for evidence in (
            "product_template", "catalog_release", "visual_identity_revision",
            "product_reference", "role_table_grants",
        ):
            self.assertIn(evidence, sql)

    def test_mapping_stays_explicitly_unapproved(self) -> None:
        mapping = (ROOT / "docs/MAPPING-COMPANY-BRAND-INICIAL.md").read_text(encoding="utf-8")
        self.assertIn("PENDIENTE", mapping)
        self.assertIn("Bloqueado por lista", mapping)
        self.assertIn("No se permite asignar automáticamente", mapping)


if __name__ == "__main__":
    unittest.main()
