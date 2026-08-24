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

    def test_apply_role_permissions_are_exact(self) -> None:
        def table_privilege(table: str, privilege: str) -> bool:
            return bool(
                self.connection.execute(
                    "SELECT has_table_privilege('perfect_catalog_app', %s, %s)",
                    (f"perfect_catalog.{table}", privilege),
                ).fetchone()[0]
            )

        def column_privilege(table: str, column: str, privilege: str = "UPDATE") -> bool:
            return bool(
                self.connection.execute(
                    "SELECT has_column_privilege('perfect_catalog_app', %s, %s, %s)",
                    (f"perfect_catalog.{table}", column, privilege),
                ).fetchone()[0]
            )

        self.assertFalse(table_privilege("import_batch", "UPDATE"))
        self.assertTrue(table_privilege("import_file", "SELECT"))
        self.assertTrue(table_privilege("import_plan_item", "SELECT"))
        self.assertTrue(column_privilege("import_batch", "status"))
        self.assertTrue(column_privilege("import_batch", "statistics"))
        self.assertFalse(column_privilege("import_batch", "scope"))
        self.assertTrue(column_privilege("import_plan", "plan_status"))
        self.assertFalse(column_privilege("import_plan", "plan_sha256"))
        self.assertTrue(column_privilege("source_system", "updated_at"))
        self.assertFalse(column_privilege("source_system", "code"))
        for table in (
            "brand",
            "product_category",
            "product_template",
            "product_reference",
            "inventory_snapshot",
            "audit_event",
        ):
            with self.subTest(table=table):
                self.assertTrue(table_privilege(table, "INSERT"))
                self.assertFalse(table_privilege(table, "DELETE"))

    def test_approve_apply_and_retry_as_application_role(self) -> None:
        from perfect_catalog.application import (
            _apply_plan_in_connection,
            _approve_plan_in_connection,
        )
        from perfect_catalog.importer import (
            CONTRACT_VERSION,
            RULES_VERSION,
            approval_fingerprint,
            plan_hash,
            plan_item_hash,
        )

        ids = {
            name: uuid.uuid4()
            for name in ("source", "batch", "file", "row", "plan", "product")
        }
        now = datetime.now(UTC)
        file_sha = "a" * 64

        def make_item(order: int, operation: str, proposed: dict[str, object]) -> dict[str, object]:
            item: dict[str, object] = {
                "import_plan_item_id": uuid.uuid5(ids["plan"], f"item:{order}:{operation}"),
                "import_plan_id": ids["plan"],
                "import_file_id": ids["file"],
                "item_order": order,
                "staging_row_id": ids["row"],
                "resolved_product_template_id": None,
                "resolved_product_variant_id": None,
                "planned_product_template_id": ids["product"],
                "planned_product_variant_id": None,
                "operation_type": operation,
                "before_values": {},
                "proposed_values": proposed,
                "issues": [],
                "requires_review": True,
            }
            item["item_sha256"] = plan_item_hash(item)
            return item

        items = [
            make_item(
                1,
                "create",
                {
                    "brand": "NATSUKI",
                    "family": "empaques",
                    "source_model": "product.template",
                    "name_original": "Producto sintético apply",
                    "internal_reference_original": f"SYN-{ids['product']}",
                    "internal_reference_normalized": f"SYN-{ids['product']}".upper(),
                    "category_path": "Synthetic / Apply",
                    "currency": "USD",
                    "activity_state": None,
                    "is_favorite": False,
                    "variant_count_observed": None,
                    "uom_original": "Units",
                    "show_quantity_status": True,
                    "source_updated_at": None,
                    "catalog_status": "pending_review",
                    "source_active": None,
                },
            ),
            make_item(
                2,
                "inventory_snapshot",
                {
                    "quantity_on_hand": -2,
                    "quantity_available": 0,
                    "uom_original": "Units",
                    "source_date_serial": 46000.5,
                    "source_updated_at": None,
                },
            ),
            make_item(3, "media_pending", {"status": "presente", "decoded": False}),
        ]
        digest = plan_hash(file_sha, items)
        fingerprint = approval_fingerprint(file_sha, digest)

        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO perfect_catalog.source_system
                (source_system_id,code,name,system_type)
            VALUES (%s,%s,'Synthetic apply','test')
            """,
            (ids["source"], f"apply-{ids['source']}"),
        )
        cursor.execute(
            """
            INSERT INTO perfect_catalog.import_batch
                (import_batch_id,source_system_id,mode,status,scope,started_at,requested_by)
            VALUES (%s,%s,'dry_run','awaiting_review',%s,%s,'integration-test')
            """,
            (ids["batch"], ids["source"], Jsonb({"synthetic": True}), now),
        )
        cursor.execute(
            """
            INSERT INTO perfect_catalog.import_file
                (import_file_id,import_batch_id,original_name,storage_uri,size_bytes,sha256,
                 media_type,received_at)
            VALUES (%s,%s,'synthetic.xlsx','synthetic/not-read',1,%s,'application/test',%s)
            """,
            (ids["file"], ids["batch"], file_sha, now),
        )
        cursor.execute(
            """
            INSERT INTO perfect_catalog.staging_row
                (staging_row_id,import_file_id,sheet_name,source_row_number,raw_headers,raw_values,
                 raw_excel_serials,structural_metadata,row_sha256)
            VALUES (%s,%s,'Synthetic',2,%s,%s,%s,%s,%s)
            """,
            (
                ids["row"],
                ids["file"],
                Jsonb([]),
                Jsonb({}),
                Jsonb({}),
                Jsonb({}),
                "b" * 64,
            ),
        )
        cursor.execute(
            """
            INSERT INTO perfect_catalog.import_plan
                (import_plan_id,import_batch_id,import_file_id,file_sha256,contract_version,
                 rules_version,plan_status,plan_sha256,approval_fingerprint_sha256,
                 generated_at,generated_by)
            VALUES (%s,%s,%s,%s,%s,%s,'awaiting_review',%s,%s,%s,'integration-test')
            """,
            (
                ids["plan"],
                ids["batch"],
                ids["file"],
                file_sha,
                CONTRACT_VERSION,
                RULES_VERSION,
                digest,
                fingerprint,
                now,
            ),
        )
        for item in items:
            cursor.execute(
                """
                INSERT INTO perfect_catalog.import_plan_item
                    (import_plan_item_id,import_plan_id,import_file_id,item_order,staging_row_id,
                     resolved_product_template_id,resolved_product_variant_id,
                     planned_product_template_id,planned_product_variant_id,operation_type,
                     before_values,proposed_values,issues,requires_review,item_sha256)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    item["import_plan_item_id"],
                    item["import_plan_id"],
                    item["import_file_id"],
                    item["item_order"],
                    item["staging_row_id"],
                    item["resolved_product_template_id"],
                    item["resolved_product_variant_id"],
                    item["planned_product_template_id"],
                    item["planned_product_variant_id"],
                    item["operation_type"],
                    Jsonb(item["before_values"]),
                    Jsonb(item["proposed_values"]),
                    Jsonb(item["issues"]),
                    item["requires_review"],
                    item["item_sha256"],
                ),
            )

        self.connection.execute("SET ROLE perfect_catalog_app")
        approved = _approve_plan_in_connection(
            self.connection,
            ids["plan"],
            fingerprint,
            "integration-reviewer",
            "synthetic approval",
            verify_source=False,
        )
        self.assertEqual(approved["status"], "approved")

        applied = _apply_plan_in_connection(
            self.connection,
            ids["plan"],
            fingerprint,
            "integration-reviewer",
            "synthetic apply",
            verify_source=False,
        )
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(applied["counts"]["create"], 1)
        self.assertEqual(applied["counts"]["inventory_snapshot"], 1)
        self.assertEqual(applied["counts"]["media_pending"], 1)

        retried = _apply_plan_in_connection(
            self.connection,
            ids["plan"],
            fingerprint,
            "integration-reviewer",
            "synthetic retry",
            verify_source=False,
        )
        self.assertEqual(retried["status"], "already_applied")
        self.connection.execute("RESET ROLE")
        counts = self.connection.execute(
            """
            SELECT
                (SELECT count(*) FROM perfect_catalog.product_template
                 WHERE product_template_id=%s),
                (SELECT count(*) FROM perfect_catalog.product_reference
                 WHERE product_template_id=%s),
                (SELECT count(*) FROM perfect_catalog.inventory_snapshot
                 WHERE import_plan_id=%s),
                (SELECT count(*) FROM perfect_catalog.audit_event
                 WHERE import_plan_id=%s)
            """,
            (ids["product"], ids["product"], ids["plan"], ids["plan"]),
        ).fetchone()
        self.assertEqual(counts, (1, 1, 1, 4))
        variant_count = self.connection.execute(
            "SELECT variant_count_observed FROM perfect_catalog.product_template WHERE product_template_id=%s",
            (ids["product"],),
        ).fetchone()[0]
        self.assertIsNone(variant_count)

    def test_published_release_read_model_as_application_role(self) -> None:
        from perfect_catalog.releases import (
            RELEASE_HASH_ALGORITHM,
            SNAPSHOT_SCHEMA_VERSION,
            product_snapshot_sha256,
            release_snapshot_sha256,
        )
        from perfect_catalog.web import ReleaseCatalogRepository

        ids = {
            name: uuid.uuid4()
            for name in (
                "source",
                "batch",
                "file",
                "row",
                "brand",
                "product",
                "release",
                "release_item",
            )
        }
        now = datetime.now(UTC)
        snapshot_data = {
            "product_template_id": str(ids["product"]),
            "product_variant_id": None,
            "source_row_number": 2,
            "internal_reference_original": "REL-001",
            "internal_reference_normalized": "REL-001",
            "name_original": "Producto release sintético",
            "name_normalized": "PRODUCTO RELEASE SINTÉTICO",
            "category_path": "Empaques / Publicados",
            "quantity_available": 0,
            "image_status": "absent",
            "brand": "NATSUKI",
            "family": "empaques",
        }
        item = {
            "item_order": 1,
            "product_template_id": ids["product"],
            "product_variant_id": None,
            "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
            "snapshot_data": snapshot_data,
            "snapshot_sha256": product_snapshot_sha256(snapshot_data),
        }
        release_sha = release_snapshot_sha256(ids["brand"], "2026.08.24-test", [item])
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO perfect_catalog.source_system
                (source_system_id,code,name,system_type)
            VALUES (%s,%s,'Release synthetic','test')
            """,
            (ids["source"], f"release-{ids['source']}"),
        )
        cursor.execute(
            """
            INSERT INTO perfect_catalog.import_batch
                (import_batch_id,source_system_id,mode,status,scope,started_at,finished_at)
            VALUES (%s,%s,'apply','completed',%s,%s,%s)
            """,
            (ids["batch"], ids["source"], Jsonb({"synthetic": True}), now, now),
        )
        cursor.execute(
            """
            INSERT INTO perfect_catalog.import_file
                (import_file_id,import_batch_id,original_name,storage_uri,size_bytes,sha256,
                 media_type,received_at)
            VALUES (%s,%s,'release.xlsx','synthetic/release',1,%s,'application/test',%s)
            """,
            (ids["file"], ids["batch"], "a" * 64, now),
        )
        cursor.execute(
            """
            INSERT INTO perfect_catalog.staging_row
                (staging_row_id,import_file_id,sheet_name,source_row_number,raw_headers,raw_values,
                 raw_excel_serials,structural_metadata,row_sha256)
            VALUES (%s,%s,'Synthetic',2,%s,%s,%s,%s,%s)
            """,
            (
                ids["row"],
                ids["file"],
                Jsonb([]),
                Jsonb({}),
                Jsonb({}),
                Jsonb({}),
                "b" * 64,
            ),
        )
        cursor.execute(
            """
            INSERT INTO perfect_catalog.brand
                (brand_id,source_system_id,code,name,normalized_name)
            VALUES (%s,%s,'NATSUKI','Natsuki','NATSUKI')
            """,
            (ids["brand"], ids["source"]),
        )
        cursor.execute(
            """
            INSERT INTO perfect_catalog.product_template
                (product_template_id,source_system_id,brand_id,name_original,
                 variant_count_observed,created_from_staging_row_id,last_confirmed_batch_id)
            VALUES (%s,%s,%s,'Producto release sintético',NULL,%s,%s)
            """,
            (ids["product"], ids["source"], ids["brand"], ids["row"], ids["batch"]),
        )
        cursor.execute(
            """
            INSERT INTO perfect_catalog.catalog_release
                (catalog_release_id,brand_id,version,status,definition,created_at,created_by,
                 published_at,published_by,snapshot_sha256)
            VALUES (%s,%s,'2026.08.24-test','published',%s,%s,'integration-test',
                    %s,'integration-test',%s)
            """,
            (
                ids["release"],
                ids["brand"],
                Jsonb({
                    "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
                    "release_hash_algorithm": RELEASE_HASH_ALGORITHM,
                }),
                now,
                now,
                release_sha,
            ),
        )
        cursor.execute(
            """
            INSERT INTO perfect_catalog.catalog_release_item
                (catalog_release_item_id,catalog_release_id,brand_id,product_template_id,
                 product_variant_id,item_order,snapshot_schema_version,snapshot_data,
                 snapshot_sha256,section_key,grouping_keys,source_import_batch_id)
            VALUES (%s,%s,%s,%s,NULL,1,%s,%s,%s,'empaques',%s,%s)
            """,
            (
                ids["release_item"],
                ids["release"],
                ids["brand"],
                ids["product"],
                SNAPSHOT_SCHEMA_VERSION,
                Jsonb(snapshot_data),
                item["snapshot_sha256"],
                Jsonb({"category": "Empaques / Publicados"}),
                ids["batch"],
            ),
        )

        self.connection.execute("SET ROLE perfect_catalog_app")
        repository = ReleaseCatalogRepository.from_connection(self.connection)
        self.assertEqual(repository.plan(), ("published:2026.08.24-test", 1, 1))
        results = repository.search("release", "Publicados", 10, 0)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], str(ids["product"]))
        self.assertEqual(results[0]["identity_status"], "published_uuid")
        self.assertEqual(results[0]["data"]["quantity_available"], 0)
        self.assertEqual(
            repository.categories(),
            [{"value": "Empaques / Publicados", "count": 1}],
        )
        self.assertIsNotNone(repository.product(str(ids["product"])))
        self.assertIsNone(repository.product("source-row:2"))

        self.connection.execute("RESET ROLE")
        self.connection.execute(
            """
            UPDATE perfect_catalog.catalog_release_item
            SET snapshot_data = snapshot_data || '{"name_original":"alterado"}'::jsonb
            WHERE catalog_release_item_id=%s
            """,
            (ids["release_item"],),
        )
        self.connection.execute("SET ROLE perfect_catalog_app")
        with self.assertRaisesRegex(ValueError, "snapshot_sha256"):
            ReleaseCatalogRepository.from_connection(self.connection)


if __name__ == "__main__":
    unittest.main()
