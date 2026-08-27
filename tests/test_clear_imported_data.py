from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ClearImportedDataScriptTests(unittest.TestCase):
    def test_reset_rebuilds_all_migrations_in_order(self) -> None:
        sql = (ROOT / "db/bootstrap/reset_imported_data.sql").read_text(encoding="utf-8")
        expected = ["apply_initial_schema.sql"] + [
            "apply_followup_migration.sql",
            "apply_apply_workflow_migration.sql",
            "apply_application_reads_migration.sql",
            "apply_release_publication_migration.sql",
            "apply_product_review_migration.sql",
            "apply_intake_migration.sql",
            "apply_intake_promotion_migration.sql",
            "apply_image_archive_index_migration.sql",
            "apply_image_match_review_migration.sql",
            "apply_approved_image_materialization_migration.sql",
            "apply_vehicle_application_workflow_migration.sql",
        ]
        positions = [sql.index(name) for name in expected]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("DROP SCHEMA IF EXISTS perfect_catalog CASCADE;", sql)

    def test_runner_is_confirmed_backed_up_and_scoped(self) -> None:
        script = (ROOT / "db/bootstrap/clear_imported_data.ps1").read_text(encoding="utf-8")
        self.assertIn("LIMPIAR IMPORTACIONES", script)
        self.assertLess(script.index("& $pgDumpPath"), script.index("& $psqlPath"))
        self.assertIn("$activeFolders = @('imports', 'intake', 'images', 'exports')", script)
        self.assertIn("Assert-ChildPath -Candidate $source -Parent $dataRoot", script)
        self.assertNotIn("'backups'", script.split("$activeFolders =", 1)[1].splitlines()[0])
        self.assertIn("Move-Item", script)
        self.assertNotIn("Remove-Item -Recurse", script)

    def test_public_launcher_calls_guarded_runner(self) -> None:
        launcher = (ROOT / "LIMPIAR-IMPORTACIONES.cmd").read_text(encoding="utf-8")
        self.assertIn("db\\bootstrap\\clear_imported_data.ps1", launcher)


if __name__ == "__main__":
    unittest.main()
