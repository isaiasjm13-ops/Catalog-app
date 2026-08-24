from __future__ import annotations

import getpass
import os
import unittest
import uuid
from datetime import UTC, datetime

try:
    import psycopg
    from psycopg.types.json import Jsonb
except ImportError:  # pragma: no cover - allows static-only environments
    psycopg = None
    Jsonb = None


RUN_INTEGRATION = os.getenv("PERFECT_CATALOG_RUN_INTEGRATION") == "1"


@unittest.skipUnless(RUN_INTEGRATION and psycopg is not None, "PostgreSQL integration tests are opt-in")
class PostgreSQLSchemaIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        password = getpass.getpass("Contraseña de postgres para pruebas transaccionales (oculta): ")
        cls.connection = psycopg.connect(
            host=os.getenv("PGHOST", "localhost"),
            port=int(os.getenv("PGPORT", "5432")),
            dbname=os.getenv("PGDATABASE", "perfect_catalog_dev"),
            user=os.getenv("PERFECT_CATALOG_INTEGRATION_USER", "postgres"),
            password=password,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.connection.close()

    def setUp(self) -> None:
        self.connection.rollback()
        self.connection.execute("SET ROLE perfect_catalog_owner")

    def tearDown(self) -> None:
        self.connection.rollback()

    def test_database_and_real_catalog_counts(self) -> None:
        row = self.connection.execute(
            """
            SELECT current_database(), pg_encoding_to_char(encoding), datlocprovider,
                   datlocale, pg_catalog.pg_get_userbyid(datdba),
                   current_setting('TimeZone')
            FROM pg_database WHERE datname = current_database()
            """
        ).fetchone()
        self.assertEqual(row, ("perfect_catalog_dev", "UTF8", "i", "es-PA", "perfect_catalog_owner", "UTC"))

        counts = self.connection.execute(
            """
            SELECT
              (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
               WHERE n.nspname='perfect_catalog' AND c.relkind='r'),
              (SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace
               WHERE n.nspname='perfect_catalog' AND c.contype='p'),
              (SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace
               WHERE n.nspname='perfect_catalog' AND c.contype='f'),
              (SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace
               WHERE n.nspname='perfect_catalog' AND c.contype='c'),
              (SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace
               WHERE n.nspname='perfect_catalog' AND c.contype='u'),
              (SELECT count(*) FROM pg_index i JOIN pg_class t ON t.oid=i.indrelid
               JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='perfect_catalog'),
              (SELECT count(*) FROM information_schema.columns
               WHERE table_schema='perfect_catalog' AND is_generated='ALWAYS'),
              (SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace
               WHERE n.nspname='perfect_catalog' AND c.contype='f' AND c.confdeltype='c')
            """
        ).fetchone()
        self.assertEqual(counts, (24, 24, 59, 174, 21, 126, 6, 0))

    def test_future_existing_snapshot_variant_and_invalid_contexts(self) -> None:
        ids = {name: uuid.uuid4() for name in (
            "source", "batch", "file", "file2", "row", "row2", "plan", "plan2",
            "brand", "existing", "future", "future_variant", "existing_variant",
        )}
        now = datetime.now(UTC)
        cursor = self.connection.cursor()
        cursor.execute(
            "INSERT INTO perfect_catalog.source_system (source_system_id,code,name,system_type) VALUES (%s,%s,'Synthetic','test')",
            (ids["source"], f"integration-{ids['source']}"),
        )
        cursor.execute(
            "INSERT INTO perfect_catalog.import_batch (import_batch_id,source_system_id,mode,status,scope,started_at) VALUES (%s,%s,'dry_run','awaiting_review',%s,%s)",
            (ids["batch"], ids["source"], Jsonb({}), now),
        )
        for file_key in ("file", "file2"):
            cursor.execute(
                """
                INSERT INTO perfect_catalog.import_file
                (import_file_id,import_batch_id,original_name,storage_uri,size_bytes,sha256,media_type,received_at)
                VALUES (%s,%s,%s,%s,1,%s,'application/test',%s)
                """,
                (ids[file_key], ids["batch"], f"{file_key}.xlsx", f"synthetic/{file_key}", "a" * 64, now),
            )
        for row_key, file_key, number in (("row", "file", 2), ("row2", "file2", 2)):
            cursor.execute(
                """
                INSERT INTO perfect_catalog.staging_row
                (staging_row_id,import_file_id,sheet_name,source_row_number,raw_headers,raw_values,
                 raw_excel_serials,structural_metadata,row_sha256)
                VALUES (%s,%s,'Synthetic',%s,%s,%s,%s,%s,%s)
                """,
                (ids[row_key], ids[file_key], number, Jsonb([]), Jsonb({}), Jsonb({}), Jsonb({}), "b" * 64),
            )
        for plan_key, file_key in (("plan", "file"), ("plan2", "file2")):
            cursor.execute(
                """
                INSERT INTO perfect_catalog.import_plan
                (import_plan_id,import_batch_id,import_file_id,file_sha256,contract_version,rules_version,
                 plan_status,plan_sha256,approval_fingerprint_sha256,generated_at,generated_by)
                VALUES (%s,%s,%s,%s,'test-contract','test-rules','awaiting_review',%s,%s,%s,'integration-test')
                """,
                (ids[plan_key], ids["batch"], ids[file_key], "a" * 64, "c" * 64, "d" * 64, now),
            )
        cursor.execute(
            "INSERT INTO perfect_catalog.brand (brand_id,source_system_id,code,name,normalized_name) VALUES (%s,%s,%s,'Synthetic','SYNTHETIC')",
            (ids["brand"], ids["source"], f"S-{ids['brand']}"),
        )
        cursor.execute(
            """
            INSERT INTO perfect_catalog.product_template
            (product_template_id,source_system_id,brand_id,name_original,variant_count_observed,created_from_staging_row_id)
            VALUES (%s,%s,%s,'Synthetic existing',1,%s)
            """,
            (ids["existing"], ids["source"], ids["brand"], ids["row"]),
        )
        cursor.execute(
            """
            INSERT INTO perfect_catalog.product_variant
            (product_variant_id,product_template_id,source_system_id,odoo_variant_id,created_from_staging_row_id)
            VALUES (%s,%s,%s,'synthetic-variant',%s)
            """,
            (ids["existing_variant"], ids["existing"], ids["source"], ids["row"]),
        )

        def insert_item(order: int, operation: str, planned_template: uuid.UUID, resolved_template: uuid.UUID | None = None,
                        planned_variant: uuid.UUID | None = None, resolved_variant: uuid.UUID | None = None,
                        plan: str = "plan", file: str = "file", row: str = "row") -> uuid.UUID:
            item_id = uuid.uuid4()
            cursor.execute(
                """
                INSERT INTO perfect_catalog.import_plan_item
                (import_plan_item_id,import_plan_id,import_file_id,item_order,staging_row_id,
                 resolved_product_template_id,resolved_product_variant_id,
                 planned_product_template_id,planned_product_variant_id,operation_type,
                 before_values,proposed_values,issues,requires_review,item_sha256)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,true,%s)
                """,
                (
                    item_id, ids[plan], ids[file], order, ids[row], resolved_template, resolved_variant,
                    planned_template, planned_variant, operation, Jsonb({}), Jsonb({}), Jsonb([]), "e" * 64,
                ),
            )
            return item_id

        insert_item(1, "create", ids["future"])
        insert_item(2, "update", ids["existing"], resolved_template=ids["existing"])
        snapshot_item = insert_item(3, "inventory_snapshot", ids["future"])
        insert_item(4, "create", ids["future"], planned_variant=ids["future_variant"])

        cursor.execute(
            """
            INSERT INTO perfect_catalog.product_template
            (product_template_id,source_system_id,brand_id,name_original,variant_count_observed,created_from_staging_row_id)
            VALUES (%s,%s,%s,'Synthetic future',0,%s)
            """,
            (ids["future"], ids["source"], ids["brand"], ids["row"]),
        )
        cursor.execute(
            """
            INSERT INTO perfect_catalog.inventory_snapshot
            (inventory_snapshot_id,product_template_id,import_batch_id,import_plan_id,import_plan_item_id,
             import_file_id,staging_row_id,quantity_on_hand,quantity_available,uom_original,captured_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,-1,0,'Units',%s)
            """,
            (uuid.uuid4(), ids["future"], ids["batch"], ids["plan"], snapshot_item, ids["file"], ids["row"], now),
        )

        with self.assertRaises(psycopg.errors.CheckViolation):
            with self.connection.transaction():
                insert_item(5, "update", ids["future"], resolved_template=ids["existing"])
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            with self.connection.transaction():
                insert_item(6, "create", uuid.uuid4(), plan="plan", file="file2", row="row2")


if __name__ == "__main__":
    unittest.main()
