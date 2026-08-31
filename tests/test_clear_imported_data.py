from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ClearImportedDataScriptTests(unittest.TestCase):
    def test_reset_rebuilds_all_migrations_in_order(self) -> None:
        sql = (ROOT / "db/bootstrap/reset_imported_data.sql").read_text(encoding="utf-8")
        expected = ["apply_initial_schema.sql"] + [
            f"../migrations/{version:04d}_" for version in range(2, 21)
        ]
        positions = [sql.index(name) for name in expected]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("DROP SCHEMA IF EXISTS perfect_catalog CASCADE;", sql)

    def test_runner_is_confirmed_backed_up_and_scoped(self) -> None:
        script = (ROOT / "db/bootstrap/clear_imported_data.ps1").read_text(encoding="utf-8")
        self.assertIn("LIMPIAR IMPORTACIONES", script)
        self.assertLess(script.index("& $pgDumpPath"), script.index("& $psqlPath"))
        self.assertIn('"checksum_0017=$checksum0017"', script)
        self.assertIn('"checksum_0018=$checksum0018"', script)
        self.assertIn('"checksum_0019=$checksum0019"', script)
        self.assertIn('"checksum_0020=$checksum0020"', script)
        self.assertIn("$activeFolders = @('imports', 'intake', 'images', 'exports')", script)
        self.assertIn("Assert-ChildPath -Candidate $source -Parent $dataRoot", script)
        self.assertNotIn("'backups'", script.split("$activeFolders =", 1)[1].splitlines()[0])
        self.assertIn("Move-Item", script)
        self.assertIn("$_.Name -ne '.gitkeep'", script)
        self.assertNotIn("Remove-Item -Recurse", script)

    def test_public_launcher_calls_guarded_runner(self) -> None:
        launcher = (ROOT / "LIMPIAR-IMPORTACIONES.cmd").read_text(encoding="utf-8")
        self.assertIn("db\\bootstrap\\clear_imported_data.ps1", launcher)


if __name__ == "__main__":
    unittest.main()
