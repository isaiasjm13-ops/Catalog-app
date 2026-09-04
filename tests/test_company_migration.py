from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CompanyMigrationTests(unittest.TestCase):
    def test_ledger_is_owner_controlled_and_checksum_bound(self) -> None:
        sql = (ROOT / "db/migrations/0017_migration_ledger.sql").read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE perfect_catalog.schema_migration", sql)
        self.assertIn("checksum_sha256 char(64) NOT NULL", sql)
        self.assertIn("VALUES (\n    '0017_migration_ledger', :'checksum_0017'", sql)
        self.assertIn("REVOKE ALL ON perfect_catalog.schema_migration FROM PUBLIC", sql)
        self.assertNotIn("perfect_catalog_app;", sql)

    def test_company_backfill_is_explicit_complete_and_non_destructive(self) -> None:
        sql = (ROOT / "db/migrations/0018_companies.sql").read_text(encoding="utf-8")
        for code in ("PERFECT", "KMC", "NATSUKI", "MASAKI", "PDM"):
            self.assertIn(f"'{code}'", sql)
        self.assertIn("WHEN 'EXACTCARS' THEN", sql)
        self.assertIn("WHEN 'NATSUKI' THEN", sql)
        self.assertIn("Hay marcas sin mapping Company", sql)
        self.assertIn("ALTER COLUMN company_id SET NOT NULL", sql)
        self.assertIn("ON DELETE RESTRICT", sql)
        self.assertNotIn("DELETE FROM perfect_catalog.schema_migration", sql.upper())
        self.assertNotIn("DROP ", sql.upper())

    def test_updater_calculates_checksums_instead_of_hardcoding_them(self) -> None:
        script = (ROOT / "db/bootstrap/run_pending_migrations.ps1").read_text(encoding="utf-8")
        self.assertIn("Get-FileHash -LiteralPath $migration0017 -Algorithm SHA256", script)
        self.assertIn("Get-FileHash -LiteralPath $migration0018 -Algorithm SHA256", script)
        self.assertIn('"checksum_0017=$checksum0017"', script)
        self.assertIn('"checksum_0018=$checksum0018"', script)
        self.assertIn("Get-FileHash -LiteralPath $migration0019 -Algorithm SHA256", script)
        self.assertIn('"checksum_0019=$checksum0019"', script)
        self.assertIn("Get-FileHash -LiteralPath $migration0020 -Algorithm SHA256", script)
        self.assertIn('"checksum_0020=$checksum0020"', script)
        self.assertIn("Get-FileHash -LiteralPath $migration0021 -Algorithm SHA256", script)
        self.assertIn('"checksum_0021=$checksum0021"', script)
        self.assertIn("Get-FileHash -LiteralPath $migration0022 -Algorithm SHA256", script)
        self.assertIn('"checksum_0022=$checksum0022"', script)
        self.assertIn("actualizar-sistema-ultimo.log", script)
        self.assertIn("Tee-Object -FilePath $logPath", script)

    def test_updater_enforces_post_migration_company_invariants(self) -> None:
        sql = (ROOT / "db/bootstrap/apply_pending_migrations.sql").read_text(encoding="utf-8")
        self.assertIn("faltan entradas 0017-0026 en el ledger", sql)
        self.assertIn("SELECT 1 FROM perfect_catalog.brand WHERE company_id IS NULL", sql)
        self.assertIn("b.code = 'EXACTCARS' AND c.code <> 'PERFECT'", sql)
        self.assertIn("b.code = 'MASAKI' AND c.code <> 'PERFECT'", sql)
        self.assertIn("b.code = 'NATSUKI' AND c.code <> 'NATSUKI'", sql)
        self.assertIn("NATSUKI debe existir como Company activa", sql)
        self.assertIn("Base de datos actualizada y validada", sql)

    def test_company_identity_migration_scopes_profiles_and_company_logos(self) -> None:
        sql = (ROOT / "db/migrations/0019_company_visual_identity.sql").read_text(encoding="utf-8")
        self.assertIn("ALTER TABLE perfect_catalog.brand_profile", sql)
        self.assertIn("ALTER COLUMN company_id SET NOT NULL", sql)
        self.assertIn("UPDATE perfect_catalog.brand_profile AS bp", sql)
        self.assertIn("COALESCE(\n    b.company_id", sql)
        self.assertIn("'2ec779ba-2355-5151-babd-704cfa8f3ef0'::uuid", sql)
        self.assertIn("scope='company' AND company_id IS NOT NULL", sql)
        self.assertIn("fk_visual_identity_revision_company", sql)
        self.assertIn("'0019_company_visual_identity', :'checksum_0019'", sql)
        self.assertNotIn("DELETE FROM", sql.upper())

    def test_company_administration_corrects_brand_ownership_without_deleting_history(self) -> None:
        sql = (ROOT / "db/migrations/0021_company_administration.sql").read_text(encoding="utf-8")
        self.assertIn("code IN ('NATSUKI','MASAKI')", sql)
        self.assertIn("SET company_id='2ec779ba-2355-5151-babd-704cfa8f3ef0'", sql)
        self.assertIn("company_admin_event", sql)
        self.assertIn("trg_company_admin_event_append_only", sql)
        self.assertIn("SET is_active=false", sql)
        self.assertNotIn("DELETE FROM perfect_catalog.schema_migration", sql.upper())
        self.assertNotIn("UPDATE perfect_catalog.intake_submission", sql)
        self.assertNotIn("DELETE FROM perfect_catalog.intake_submission", sql)

    def test_intake_company_migration_preserves_unknown_history(self) -> None:
        sql = (ROOT / "db/migrations/0020_company_intake_context.sql").read_text(encoding="utf-8")
        self.assertIn("ALTER TABLE perfect_catalog.intake_submission", sql)
        self.assertIn("ALTER TABLE perfect_catalog.import_plan", sql)
        self.assertIn("intake_submission es append-only", sql)
        self.assertIn("UPDATE perfect_catalog.import_plan AS p", sql)
        self.assertNotIn("UPDATE perfect_catalog.intake_submission", sql)
        self.assertNotIn("FROM perfect_catalog.intake_promotion AS ip", sql)
        self.assertIn("Los ingresos anteriores sin contexto quedan", sql)
        self.assertNotIn("ALTER COLUMN company_id SET NOT NULL", sql)
        self.assertIn("trg_intake_submission_company_required", sql)
        self.assertIn("trg_import_plan_company_required", sql)
        self.assertIn("company_id es obligatorio para nuevos registros", sql)
        self.assertIn("REVOKE ALL ON FUNCTION perfect_catalog.require_company_context() FROM PUBLIC", sql)
        self.assertIn("TO perfect_catalog_app", sql)
        self.assertNotIn("DELETE FROM", sql.upper())

    def test_review_queue_keeps_company_scope_and_signature(self) -> None:
        reviews = (ROOT / "src/perfect_catalog/reviews.py").read_text(encoding="utf-8")
        api = (ROOT / "src/perfect_catalog/operator_api.py").read_text(encoding="utf-8")
        self.assertIn("company_id: uuid.UUID | None = None", reviews)
        self.assertIn("company_id=session_or_redirect.company_id", api)

    def test_natsuki_restoration_reactivates_the_legacy_row_instead_of_recreating_it(self) -> None:
        sql = (ROOT / "db/migrations/0025_natsuki_company_restored.sql").read_text(encoding="utf-8")
        self.assertTrue(sql.lstrip().startswith("BEGIN;"))
        self.assertTrue(sql.rstrip().endswith("COMMIT;"))
        self.assertIn("'ee7c7e0c-398f-5e35-9d79-c97d761f8672'::uuid", sql)
        self.assertIn("SET is_active=true", sql)
        self.assertIn("'reactivated'", sql)
        self.assertIn("UPDATE perfect_catalog.brand", sql)
        self.assertIn("UPDATE perfect_catalog.brand_profile", sql)
        self.assertNotIn("DELETE FROM", sql.upper())
        self.assertNotIn("WHERE code='MASAKI'", sql)
        self.assertNotIn("WHERE code='EXACTCARS'", sql)

    def test_natsuki_restoration_is_wired_into_the_central_updater(self) -> None:
        bootstrap = (ROOT / "db/bootstrap/apply_pending_migrations.sql").read_text(encoding="utf-8")
        self.assertIn("\\ir ../migrations/0025_natsuki_company_restored.sql", bootstrap)
        self.assertIn("checksum_0025", bootstrap)
        script = (ROOT / "db/bootstrap/run_pending_migrations.ps1").read_text(encoding="utf-8")
        self.assertIn("0025_natsuki_company_restored.sql", script)
        self.assertIn('"checksum_0025=$checksum0025"', script)

    def test_company_brand_policy_reflects_natsuki_as_its_own_company(self) -> None:
        source = (ROOT / "src/perfect_catalog/import_context.py").read_text(encoding="utf-8")
        self.assertIn("if company == 'NATSUKI':\n        return brand == 'NATSUKI'", source)
        self.assertNotIn("'NATSUKI', 'MASAKI'}:\n        return False", source)


if __name__ == "__main__":
    unittest.main()
