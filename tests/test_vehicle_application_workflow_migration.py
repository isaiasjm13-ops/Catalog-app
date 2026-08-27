from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class VehicleApplicationWorkflowMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = (ROOT / "db/migrations/0012_vehicle_application_workflow.sql").read_text(encoding="utf-8")

    def test_permissions_are_scoped_and_never_delete_evidence(self) -> None:
        self.assertIn("GRANT INSERT ON", self.sql)
        self.assertIn("product_application_candidate", self.sql)
        self.assertIn("GRANT UPDATE (review_status, reviewed_by, reviewed_at, review_note)", self.sql)
        self.assertNotRegex(self.sql, r"(?i)DELETE|TRUNCATE|DROP\s+(?:TABLE|SCHEMA)")

    def test_bootstrap_uses_owner_and_resets_role(self) -> None:
        bootstrap = (ROOT / "db/bootstrap/apply_vehicle_application_workflow_migration.sql").read_text(encoding="utf-8")
        self.assertIn("SET ROLE perfect_catalog_owner", bootstrap)
        self.assertIn("\\ir ../migrations/0012_vehicle_application_workflow.sql", bootstrap)
        self.assertTrue(bootstrap.rstrip().endswith("RESET ROLE;"))


if __name__ == "__main__":
    unittest.main()
