"""Static contract tests for the PostgreSQL schema draft.

These checks intentionally do not connect to PostgreSQL and do not replace a future
execution of the migration against PostgreSQL 16 or newer.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


SCHEMA_NAME = "perfect_catalog"
EXPECTED_TABLES = {
    "source_system",
    "import_batch",
    "import_file",
    "staging_row",
    "staging_row_result",
    "import_issue",
    "import_plan",
    "import_plan_item",
    "brand",
    "product_category",
    "product_template",
    "product_variant",
    "product_reference",
    "inventory_snapshot",
    "media_asset",
    "product_media",
    "vehicle_make",
    "vehicle_model",
    "vehicle_engine",
    "product_application_candidate",
    "extraction_candidate",
    "catalog_release",
    "catalog_release_item",
    "audit_event",
}


class SchemaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        cls.sql_path = repo_root / "db" / "migrations" / "0001_initial_schema.sql"
        cls.sql = cls.sql_path.read_text(encoding="utf-8")
        cls.sql_upper = cls.sql.upper()

    def table_body(self, table_name: str) -> str:
        marker = f"CREATE TABLE {SCHEMA_NAME}.{table_name} ("
        start = self.sql.find(marker)
        self.assertNotEqual(start, -1, f"Missing table declaration for {table_name}")
        position = start + len(marker)
        depth = 1
        in_string = False

        while position < len(self.sql):
            char = self.sql[position]
            if char == "'":
                if in_string and position + 1 < len(self.sql) and self.sql[position + 1] == "'":
                    position += 2
                    continue
                in_string = not in_string
            elif not in_string:
                if char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                    if depth == 0:
                        return self.sql[start + len(marker) : position]
            position += 1

        self.fail(f"Unclosed table declaration for {table_name}")

    def test_schema_file_exists(self) -> None:
        self.assertTrue(self.sql_path.is_file())

    def test_has_exactly_the_24_expected_tables(self) -> None:
        declarations = re.findall(
            rf"(?im)^CREATE TABLE {SCHEMA_NAME}\.([a-z][a-z0-9_]*)\s*\(",
            self.sql,
        )
        self.assertEqual(len(declarations), 24)
        self.assertEqual(set(declarations), EXPECTED_TABLES)
        self.assertEqual(len(declarations), len(set(declarations)))

    def test_all_table_declarations_are_schema_qualified(self) -> None:
        all_declarations = re.findall(
            r"(?im)^CREATE TABLE\s+([a-z][a-z0-9_.]*)\s*\(", self.sql
        )
        self.assertTrue(all_declarations)
        self.assertTrue(
            all(name.startswith(f"{SCHEMA_NAME}.") for name in all_declarations)
        )

    def test_migration_is_transactional(self) -> None:
        statements = self.sql.strip()
        self.assertRegex(statements, r"(?is)^BEGIN\s*;")
        self.assertRegex(statements, r"(?is)COMMIT\s*;\s*$")

    def test_forbidden_destructive_or_hidden_operations_are_absent(self) -> None:
        self.assertNotIn("ON DELETE CASCADE", self.sql_upper)
        self.assertNotIn("DROP TABLE", self.sql_upper)
        self.assertNotIn("DROP SCHEMA", self.sql_upper)
        self.assertNotIn("IF NOT EXISTS", self.sql_upper)

    def test_no_postgresql_extensions_are_declared(self) -> None:
        self.assertNotRegex(self.sql_upper, r"\bCREATE\s+EXTENSION\b")

    def test_source_active_is_nullable(self) -> None:
        for table_name in ("product_template", "product_variant"):
            body = self.table_body(table_name)
            declaration = re.search(r"(?im)^\s*source_active\s+boolean\s*,?\s*$", body)
            self.assertIsNotNone(declaration, f"source_active must be nullable in {table_name}")
            self.assertNotRegex(body, r"(?im)^\s*source_active\s+boolean\s+NOT NULL")

    def test_staging_row_has_no_validation_status(self) -> None:
        staging_body = self.table_body("staging_row")
        self.assertNotIn("validation_status", staging_body.lower())

    def test_versioned_results_and_persisted_plan_tables_exist(self) -> None:
        for table_name in ("staging_row_result", "import_plan", "import_plan_item"):
            self.assertIn(
                f"CREATE TABLE {SCHEMA_NAME}.{table_name}",
                self.sql,
            )

    def test_required_plan_states_exist(self) -> None:
        plan_body = self.table_body("import_plan")
        for state in (
            "generated",
            "awaiting_review",
            "approved",
            "rejected",
            "invalidated",
            "applying",
            "applied",
            "failed",
        ):
            self.assertIn(f"'{state}'", plan_body)

    def test_sha256_columns_have_hexadecimal_checks(self) -> None:
        required_constraints = (
            "ck_import_file_sha256",
            "ck_staging_row_sha256",
            "ck_staging_row_result_sha256",
            "ck_import_plan_file_sha256",
            "ck_import_plan_sha256",
            "ck_import_plan_fingerprint_sha256",
            "ck_import_plan_item_sha256",
            "ck_media_asset_sha256",
            "ck_catalog_release_sha256",
            "ck_catalog_release_item_sha256",
            "ck_audit_event_sha256",
        )
        for constraint in required_constraints:
            self.assertRegex(
                self.sql,
                rf"(?is)CONSTRAINT\s+{constraint}\s+CHECK\s*\(.*?\^\[0-9a-f\]\{{64\}}\$",
            )

    def test_confidence_columns_have_range_checks(self) -> None:
        expected = {
            "product_reference": "ck_product_reference_confidence",
            "product_application_candidate": "ck_product_application_confidence",
            "extraction_candidate": "ck_extraction_candidate_confidence",
        }
        for table_name, constraint_name in expected.items():
            body = self.table_body(table_name)
            self.assertIn(constraint_name, body)
            self.assertRegex(
                body,
                r"(?is)(?:confidence\s+IS NULL OR\s+)?confidence\s+BETWEEN 0 AND 1",
            )

    def test_value_normalized_has_no_global_unique_constraint(self) -> None:
        reference_body = self.table_body("product_reference")
        self.assertNotRegex(
            reference_body,
            r"(?is)\bUNIQUE(?:\s+NULLS\s+NOT\s+DISTINCT)?\s*\([^)]*value_normalized",
        )
        self.assertNotRegex(
            self.sql,
            r"(?is)CREATE\s+UNIQUE\s+INDEX[^;]*\([^)]*value_normalized",
        )

    def test_foreign_keys_never_request_cascading_deletes(self) -> None:
        foreign_key_count = len(re.findall(r"(?i)\bFOREIGN KEY\s*\(", self.sql))
        restrictive_count = len(
            re.findall(
                rf"(?is)FOREIGN KEY\s*\([^)]*\)\s*REFERENCES\s+{SCHEMA_NAME}\.[a-z0-9_]+\s*\([^)]*\)\s*ON DELETE RESTRICT",
                self.sql,
            )
        )
        self.assertEqual(foreign_key_count, 60)
        self.assertEqual(restrictive_count, foreign_key_count)

    def test_documented_contract_counts_remain_exact(self) -> None:
        self.assertEqual(
            len(re.findall(r"(?im)^CREATE (?:UNIQUE )?INDEX\s+", self.sql)),
            83,
        )
        self.assertEqual(
            len(re.findall(r"(?im)\bCONSTRAINT\s+ck_[a-z0-9_]+\s+CHECK\s*\(", self.sql)),
            137,
        )
        self.assertEqual(
            len(
                re.findall(
                    r"(?im)\bCONSTRAINT\s+uq_[a-z0-9_]+\s+UNIQUE(?:\s+NULLS\s+NOT\s+DISTINCT)?\s*\(",
                    self.sql,
                )
            ),
            11,
        )

    def test_staging_row_has_no_mutating_trigger(self) -> None:
        self.assertNotRegex(
            self.sql,
            rf"(?is)CREATE\s+TRIGGER\b[^;]*\bON\s+{SCHEMA_NAME}\.staging_row\b",
        )

    def test_no_enum_types_are_created(self) -> None:
        self.assertNotRegex(self.sql_upper, r"\bCREATE\s+TYPE\b")
        self.assertNotRegex(self.sql_upper, r"\bENUM\s*\(")

    def test_no_business_data_loading_statements_are_embedded(self) -> None:
        self.assertNotRegex(self.sql_upper, r"\bINSERT\s+INTO\b")
        self.assertNotRegex(self.sql_upper, r"\bCOPY\s+[A-Z0-9_.]+\s+FROM\b")
        self.assertNotRegex(self.sql_upper, r"\bVALUES\s*\(")


if __name__ == "__main__":
    unittest.main()
