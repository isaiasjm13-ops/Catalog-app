"""Static contract tests for the corrected PostgreSQL schema v0.2 draft.

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
        cls.sql_compact = re.sub(r"\s+", " ", cls.sql)

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

    def test_optional_external_identifiers_reject_blank_text(self) -> None:
        expected = {
            "source_system": ("instance_key",),
            "brand": ("source_brand_id",),
            "product_category": ("source_category_id",),
            "product_template": ("odoo_template_id", "odoo_external_id"),
            "product_variant": ("odoo_variant_id", "odoo_external_id"),
            "vehicle_make": ("source_code",),
            "vehicle_model": ("source_code",),
            "vehicle_engine": ("engine_code",),
        }
        for table_name, columns in expected.items():
            body = self.table_body(table_name)
            for column in columns:
                self.assertRegex(
                    body,
                    rf"(?is){column}\s+IS NULL\s+OR\s+btrim\({column}\)\s*<>\s*''",
                    f"{table_name}.{column} must reject blank optional identifiers",
                )

        variant_body = self.table_body("product_variant")
        real_identifier = re.search(
            r"(?is)CONSTRAINT\s+ck_product_variant_real_identifier\s+CHECK\s*\((.*?)\n\s*\),",
            variant_body,
        )
        self.assertIsNotNone(real_identifier)
        for column in ("odoo_variant_id", "odoo_external_id"):
            self.assertIn(f"btrim({column}) <> ''", real_identifier.group(1))

        for index_name, column in (
            ("uq_product_template_odoo_id", "odoo_template_id"),
            ("uq_product_template_external_id", "odoo_external_id"),
            ("uq_product_variant_odoo_id", "odoo_variant_id"),
            ("uq_product_variant_external_id", "odoo_external_id"),
        ):
            self.assertRegex(
                self.sql,
                rf"(?is)CREATE UNIQUE INDEX\s+{index_name}.*?WHERE.*?{column} IS NOT NULL.*?btrim\({column}\) <> ''\s*;",
            )

    def test_variant_shares_source_system_with_template(self) -> None:
        self.assertIn(
            "FOREIGN KEY (product_template_id, source_system_id) REFERENCES "
            "perfect_catalog.product_template (product_template_id, source_system_id)",
            self.sql_compact,
        )
        template_body = self.table_body("product_template")
        self.assertIn(
            "uq_product_template_source UNIQUE (product_template_id, source_system_id)",
            re.sub(r"\s+", " ", template_body),
        )

    def test_product_reference_shares_template_origin_and_brand(self) -> None:
        self.assertIn(
            "FOREIGN KEY (product_template_id, source_system_id, brand_id) REFERENCES "
            "perfect_catalog.product_template ( product_template_id, source_system_id, brand_id )",
            self.sql_compact,
        )
        self.assertIn(
            "FOREIGN KEY (product_template_id, product_variant_id) REFERENCES "
            "perfect_catalog.product_variant (product_template_id, product_variant_id)",
            self.sql_compact,
        )

    def test_plan_item_and_row_share_plan_file(self) -> None:
        item_body = self.table_body("import_plan_item")
        self.assertRegex(item_body, r"(?im)^\s*import_file_id\s+uuid\s+NOT NULL")
        self.assertIn(
            "FOREIGN KEY (import_plan_id, import_file_id) REFERENCES "
            "perfect_catalog.import_plan (import_plan_id, import_file_id)",
            self.sql_compact,
        )

    def test_contextual_foreign_keys_have_declared_alternate_keys(self) -> None:
        expected = {
            "staging_row": "uq_staging_row_file_row",
            "staging_row_result": "uq_staging_row_result_context",
            "import_plan": "uq_import_plan_plan_file",
            "import_plan_item": "uq_import_plan_item_snapshot_context",
            "product_template": "uq_product_template_source_brand",
            "vehicle_model": "uq_vehicle_model_make_model",
            "vehicle_engine": "uq_vehicle_engine_context",
            "catalog_release": "uq_catalog_release_release_brand",
        }
        for table_name, constraint in expected.items():
            self.assertIn(constraint, self.table_body(table_name))
        self.assertIn(
            "FOREIGN KEY (import_file_id, staging_row_id) REFERENCES "
            "perfect_catalog.staging_row (import_file_id, staging_row_id)",
            self.sql_compact,
        )

    def test_inventory_snapshot_has_exact_batch_plan_file_row_and_item_context(self) -> None:
        body = self.table_body("inventory_snapshot")
        for column in (
            "import_batch_id",
            "import_plan_id",
            "import_plan_item_id",
            "import_file_id",
            "staging_row_id",
        ):
            self.assertRegex(body, rf"(?im)^\s*{column}\s+uuid\s+NOT NULL")
        self.assertIn(
            "FOREIGN KEY (import_batch_id, import_file_id, import_plan_id) REFERENCES "
            "perfect_catalog.import_plan ( import_batch_id, import_file_id, import_plan_id )",
            self.sql_compact,
        )
        self.assertIn("fk_inventory_snapshot_exact_plan_item", self.sql)
        self.assertIn("plan_item_operation_type", body)
        self.assertIn("ck_inventory_snapshot_operation", body)
        self.assertIn("product_scope", body)
        self.assertIn("product_target_id", body)
        self.assertIn("uq_inventory_snapshot_plan_item UNIQUE (import_plan_item_id)", body)

    def test_import_issue_context_is_relationally_coherent(self) -> None:
        self.assertIn("fk_import_issue_row_in_file", self.sql)
        self.assertIn(
            "FOREIGN KEY (import_batch_id, import_file_id, staging_row_result_id) REFERENCES "
            "perfect_catalog.staging_row_result ( import_batch_id, import_file_id, staging_row_result_id )",
            self.sql_compact,
        )

    def test_release_items_cannot_mix_brands(self) -> None:
        body = self.table_body("catalog_release_item")
        self.assertRegex(body, r"(?im)^\s*brand_id\s+uuid\s+NOT NULL")
        self.assertIn(
            "FOREIGN KEY (catalog_release_id, brand_id) REFERENCES "
            "perfect_catalog.catalog_release (catalog_release_id, brand_id)",
            self.sql_compact,
        )
        self.assertIn(
            "FOREIGN KEY (product_template_id, brand_id) REFERENCES "
            "perfect_catalog.product_template (product_template_id, brand_id)",
            self.sql_compact,
        )

    def test_vehicle_relationships_use_contextual_keys(self) -> None:
        application_body = self.table_body("product_application_candidate")
        self.assertIn("ck_product_application_model_requires_make", application_body)
        self.assertIn(
            "FOREIGN KEY (vehicle_make_id, vehicle_model_id) REFERENCES "
            "perfect_catalog.vehicle_model (vehicle_make_id, vehicle_model_id)",
            self.sql_compact,
        )
        self.assertIn(
            "FOREIGN KEY (vehicle_make_id, vehicle_model_id, vehicle_engine_id) REFERENCES "
            "perfect_catalog.vehicle_engine ( vehicle_make_id, vehicle_model_id, vehicle_engine_id )",
            self.sql_compact,
        )
        engine_body = self.table_body("vehicle_engine")
        self.assertIn("ck_vehicle_engine_model_requires_make", engine_body)

    def test_reviewable_records_require_human_evidence_for_decisions(self) -> None:
        constraints = {
            "product_reference": "ck_product_reference_review_evidence",
            "product_application_candidate": "ck_product_application_review_pair",
            "extraction_candidate": "ck_extraction_candidate_review_pair",
            "vehicle_make": "ck_vehicle_make_review_evidence",
            "vehicle_model": "ck_vehicle_model_review_evidence",
            "vehicle_engine": "ck_vehicle_engine_review_evidence",
        }
        for table_name, constraint in constraints.items():
            body = self.table_body(table_name)
            self.assertIn(constraint, body)
            self.assertRegex(body, r"review_status\s+IN\s*\('approved',\s*'rejected'\)")
            self.assertIn("reviewed_by IS NOT NULL", body)
            self.assertIn("btrim(reviewed_by) <> ''", body)
            self.assertIn("reviewed_at IS NOT NULL", body)
            self.assertIn("reviewed_at IS NULL OR reviewed_at >= created_at", body)

    def test_resolved_or_accepted_issue_requires_resolution_evidence(self) -> None:
        body = self.table_body("import_issue")
        self.assertIn("ck_import_issue_resolution_evidence", body)
        self.assertIn("status = 'open'", body)
        self.assertIn("resolution_note IS NULL", body)
        self.assertRegex(body, r"status\s+IN\s*\('resolved',\s*'accepted'\)")
        self.assertIn("resolved_at IS NOT NULL", body)
        self.assertIn("resolved_by IS NOT NULL", body)
        self.assertIn("btrim(resolved_by) <> ''", body)

    def test_plan_and_release_actor_fields_reject_blank_text(self) -> None:
        expected = {
            "import_plan": ("generated_by", "approved_by", "rejected_by", "applied_by"),
            "catalog_release": ("created_by", "published_by", "archived_by"),
        }
        for table_name, columns in expected.items():
            body = self.table_body(table_name)
            for column in columns:
                self.assertIn(
                    f"btrim({column}) <> ''",
                    body,
                    f"{table_name}.{column} must reject blank actors",
                )

    def test_archived_release_requires_prior_publication_and_archive_actor(self) -> None:
        body = self.table_body("catalog_release")
        self.assertRegex(body, r"(?im)^\s*archived_by\s+text\s*,")
        self.assertIn("status IN ('published', 'archived')", body)
        self.assertIn("published_at IS NOT NULL", body)
        self.assertIn("published_by IS NOT NULL", body)
        self.assertIn(
            "status = 'archived' AND archived_at IS NOT NULL AND archived_by IS NOT NULL",
            body,
        )
        self.assertIn("archived_at >= published_at", body)

    def test_product_media_primary_flag_is_not_nullable(self) -> None:
        body = self.table_body("product_media")
        self.assertRegex(
            body,
            r"(?im)^\s*is_primary\s+boolean\s+NOT NULL\s+DEFAULT\s+false",
        )

    def test_extraction_candidate_normalized_value_is_nonempty(self) -> None:
        body = self.table_body("extraction_candidate")
        self.assertIn("ck_extraction_candidate_value_normalized_nonempty", body)
        self.assertIn("btrim(value_normalized) <> ''", body)

    def test_foreign_keys_never_request_cascading_deletes(self) -> None:
        foreign_key_count = len(re.findall(r"(?i)\bFOREIGN KEY\s*\(", self.sql))
        restrictive_count = len(
            re.findall(
                rf"(?is)FOREIGN KEY\s*\([^)]*\)\s*REFERENCES\s+{SCHEMA_NAME}\.[a-z0-9_]+\s*\([^)]*\)\s*ON DELETE RESTRICT",
                self.sql,
            )
        )
        self.assertEqual(foreign_key_count, 57)
        self.assertEqual(restrictive_count, foreign_key_count)

    def test_documented_contract_counts_remain_exact(self) -> None:
        self.assertEqual(
            len(re.findall(r"(?im)^CREATE (?:UNIQUE )?INDEX\s+", self.sql)),
            80,
        )
        self.assertEqual(
            len(re.findall(r"(?im)\bCONSTRAINT\s+ck_[a-z0-9_]+\s+CHECK\s*\(", self.sql)),
            171,
        )
        self.assertEqual(
            len(
                re.findall(
                    r"(?im)\bCONSTRAINT\s+uq_[a-z0-9_]+\s+UNIQUE(?:\s+NULLS\s+NOT\s+DISTINCT)?\s*\(",
                    self.sql,
                )
            ),
            21,
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
