from __future__ import annotations

import getpass
import io
import os
import tempfile
import unittest
import uuid
from datetime import UTC, datetime
from pathlib import Path

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
        self.assertEqual(counts, (26, 26, 60, 192, 23, 133, 6, 0))

    def test_secure_intake_as_application_role(self) -> None:
        from perfect_catalog.intake import (
            SecureIntakeService,
            _list_intake_submissions_in_connection,
            _record_intake_in_connection,
        )

        class TransactionPersistence:
            def __init__(self, connection):
                self.connection = connection

            def record_intake(self, record):
                return _record_intake_in_connection(self.connection, record)

            def intake_submissions(
                self, *, kind="all", status="all", limit=50, offset=0
            ):
                return _list_intake_submissions_in_connection(
                    self.connection,
                    kind=kind,
                    status=status,
                    limit=limit,
                    offset=offset,
                )

        self.connection.execute("SET ROLE perfect_catalog_app")
        privileges = self.connection.execute(
            """
            SELECT
              has_table_privilege('perfect_catalog_app', 'perfect_catalog.intake_asset', 'SELECT'),
              has_table_privilege('perfect_catalog_app', 'perfect_catalog.intake_asset', 'INSERT'),
              has_table_privilege('perfect_catalog_app', 'perfect_catalog.intake_asset', 'UPDATE'),
              has_table_privilege('perfect_catalog_app', 'perfect_catalog.intake_asset', 'DELETE'),
              has_table_privilege('perfect_catalog_app', 'perfect_catalog.intake_submission', 'SELECT'),
              has_table_privilege('perfect_catalog_app', 'perfect_catalog.intake_submission', 'INSERT'),
              has_table_privilege('perfect_catalog_app', 'perfect_catalog.intake_submission', 'UPDATE'),
              has_table_privilege('perfect_catalog_app', 'perfect_catalog.intake_submission', 'DELETE')
            """
        ).fetchone()
        self.assertEqual(privileges, (True, True, False, False, True, True, False, False))

        with tempfile.TemporaryDirectory() as directory:
            service = SecureIntakeService(
                Path(directory), TransactionPersistence(self.connection)
            )
            first = service.submit(
                io.BytesIO(b"%PDF-1.7\nintegration"),
                filename="manual-v2.2.pdf",
                claimed_media_type="application/pdf",
                kind="manual_pdf",
                actor="integration-user",
                reason="Documento sintético de integración",
            )
            second = service.submit(
                io.BytesIO(b"%PDF-1.7\nintegration"),
                filename="manual-duplicate.pdf",
                claimed_media_type="application/pdf",
                kind="manual_pdf",
                actor="integration-user",
                reason="Reintento sintético de integración",
            )
            rejected = service.submit(
                io.BytesIO(b"invalid-pdf"),
                filename="manual-invalid.pdf",
                claimed_media_type="application/pdf",
                kind="manual_pdf",
                actor="integration-user",
                reason="Rechazo sintético de integración",
            )
            self.assertEqual(first["validation_status"], "quarantined")
            self.assertTrue(second["duplicate_content"])
            self.assertEqual(rejected["validation_status"], "rejected")
            page = service.list(kind="manual_pdf", status="all", limit=2)
            self.assertEqual(page["filtered_count"], 3)
            self.assertEqual(len(page["items"]), 2)
            last_page = service.list(
                kind="manual_pdf", status="all", limit=2, offset=10
            )
            self.assertEqual(last_page["filtered_count"], 3)
            self.assertEqual(last_page["items"], [])
            asset_id = first["intake_asset_id"]
            submission_id = first["intake_submission_id"]
            self.connection.execute("SET ROLE perfect_catalog_owner")
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with self.connection.transaction():
                    self.connection.execute("SET ROLE perfect_catalog_app")
                    self.connection.execute(
                        "UPDATE perfect_catalog.intake_asset SET received_by='changed' WHERE intake_asset_id=%s",
                        (asset_id,),
                    )
            with self.assertRaisesRegex(psycopg.Error, "append-only"):
                with self.connection.transaction():
                    self.connection.execute("SET ROLE perfect_catalog_owner")
                    self.connection.execute(
                        "DELETE FROM perfect_catalog.intake_submission WHERE intake_submission_id=%s",
                        (submission_id,),
                    )

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
            "catalog_release",
            "catalog_release_item",
        ):
            with self.subTest(table=table):
                self.assertTrue(table_privilege(table, "INSERT"))
                self.assertFalse(table_privilege(table, "DELETE"))
        self.assertTrue(column_privilege("catalog_release", "status"))
        self.assertTrue(column_privilege("catalog_release", "published_at"))
        self.assertTrue(column_privilege("catalog_release", "archived_by"))
        self.assertFalse(column_privilege("catalog_release", "definition"))
        self.assertFalse(table_privilege("catalog_release_item", "UPDATE"))
        self.assertFalse(table_privilege("product_template", "UPDATE"))
        self.assertTrue(column_privilege("product_template", "catalog_status"))
        self.assertFalse(column_privilege("product_template", "name_original"))
        self.assertTrue(column_privilege("product_variant", "catalog_status"))
        self.assertFalse(column_privilege("product_variant", "variant_name"))
        self.assertFalse(table_privilege("product_reference", "UPDATE"))
        self.assertTrue(column_privilege("product_reference", "review_status"))
        self.assertTrue(column_privilege("product_reference", "reviewed_by"))
        self.assertFalse(column_privilege("product_reference", "value_original"))

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
            for name in (
                "source",
                "batch",
                "file",
                "row",
                "plan",
                "product",
                "product_rejected",
            )
        }
        now = datetime.now(UTC)
        file_sha = "a" * 64

        def make_item(
            order: int,
            operation: str,
            proposed: dict[str, object],
            product_id: uuid.UUID | None = None,
        ) -> dict[str, object]:
            target_id = product_id or ids["product"]
            item: dict[str, object] = {
                "import_plan_item_id": uuid.uuid5(ids["plan"], f"item:{order}:{operation}"),
                "import_plan_id": ids["plan"],
                "import_file_id": ids["file"],
                "item_order": order,
                "staging_row_id": ids["row"],
                "resolved_product_template_id": None,
                "resolved_product_variant_id": None,
                "planned_product_template_id": target_id,
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
                "create",
                {
                    "brand": "NATSUKI",
                    "family": "empaques",
                    "source_model": "product.template",
                    "name_original": "Producto sintético rechazado",
                    "internal_reference_original": f"REJ-{ids['product_rejected']}",
                    "internal_reference_normalized": f"REJ-{ids['product_rejected']}".upper(),
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
                ids["product_rejected"],
            ),
            make_item(
                3,
                "inventory_snapshot",
                {
                    "quantity_on_hand": -2,
                    "quantity_available": 0,
                    "uom_original": "Units",
                    "source_date_serial": 46000.5,
                    "source_updated_at": None,
                },
            ),
            make_item(4, "media_pending", {"status": "presente", "decoded": False}),
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
        self.assertEqual(applied["counts"]["create"], 2)
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

        from perfect_catalog.publication import (
            _archive_release_in_connection,
            _build_release_in_connection,
            _publish_release_in_connection,
        )

        with self.assertRaisesRegex(RuntimeError, "pendientes de revisi"):
            _build_release_in_connection(
                self.connection,
                ids["plan"],
                fingerprint,
                "2026.08.24-pending-must-fail",
                "integration-publisher",
                "pending products cannot be published",
                brand_name="NATSUKI",
            )
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
        self.assertEqual(counts, (1, 1, 1, 5))
        variant_count = self.connection.execute(
            "SELECT variant_count_observed FROM perfect_catalog.product_template WHERE product_template_id=%s",
            (ids["product"],),
        ).fetchone()[0]
        self.assertIsNone(variant_count)

        from perfect_catalog.web import ReleaseCatalogRepository
        from perfect_catalog.reviews import (
            _inspect_review_queue_in_connection,
            _list_review_plans_in_connection,
            _review_queue_page_in_connection,
            _review_product_in_connection,
        )

        self.connection.execute("SET ROLE perfect_catalog_app")
        listed_plan = next(
            plan
            for plan in _list_review_plans_in_connection(self.connection)
            if plan["import_plan_id"] == str(ids["plan"])
        )
        self.assertEqual(listed_plan["candidate_count"], 2)
        self.assertEqual(listed_plan["pending_count"], 2)
        exact_plans = _list_review_plans_in_connection(
            self.connection, limit=1, plan_id=ids["plan"]
        )
        self.assertEqual(
            [plan["import_plan_id"] for plan in exact_plans],
            [str(ids["plan"])],
        )
        first_page = _review_queue_page_in_connection(
            self.connection,
            ids["plan"],
            fingerprint,
            state="pending",
            limit=1,
        )
        self.assertEqual(first_page["candidate_count"], 2)
        self.assertEqual(first_page["filtered_count"], 2)
        self.assertEqual(len(first_page["items"]), 1)
        past_last_page = _review_queue_page_in_connection(
            self.connection,
            ids["plan"],
            fingerprint,
            state="pending",
            limit=1,
            offset=50,
        )
        self.assertEqual(past_last_page["filtered_count"], 2)
        self.assertEqual(past_last_page["items"], [])
        searched_page = _review_queue_page_in_connection(
            self.connection,
            ids["plan"],
            fingerprint,
            query="REJ-",
            state="pending",
            limit=50,
        )
        self.assertEqual(searched_page["filtered_count"], 1)
        self.assertEqual(
            searched_page["items"][0]["product_id"],
            str(ids["product_rejected"]),
        )
        review_queue = _inspect_review_queue_in_connection(
            self.connection, ids["plan"], fingerprint
        )
        self.assertEqual(review_queue["candidate_count"], 2)
        self.assertEqual(review_queue["pending_count"], 2)
        review_item = next(
            item
            for item in review_queue["items"]
            if item["product_id"] == str(ids["product"])
        )
        rejected_review_item = next(
            item
            for item in review_queue["items"]
            if item["product_id"] == str(ids["product_rejected"])
        )
        with self.assertRaises(psycopg.errors.RaiseException):
            with self.connection.transaction():
                self.connection.execute(
                    """
                    UPDATE perfect_catalog.product_template
                    SET catalog_status='active', updated_at=%s
                    WHERE product_template_id=%s
                    """,
                    (datetime.now(UTC), ids["product"]),
                )
                self.connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
        with self.assertRaisesRegex(PermissionError, "review_sha256"):
            _review_product_in_connection(
                self.connection,
                ids["plan"],
                ids["product"],
                fingerprint,
                "0" * 64,
                "approve",
                "integration-reviewer",
                "wrong evidence must fail",
            )
        reviewed = _review_product_in_connection(
            self.connection,
            ids["plan"],
            ids["product"],
            fingerprint,
            review_item["review_sha256"],
            "approve",
            "integration-reviewer",
            "synthetic publication approval",
        )
        self.assertEqual(reviewed["status"], "approved")
        rejected = _review_product_in_connection(
            self.connection,
            ids["plan"],
            ids["product_rejected"],
            fingerprint,
            rejected_review_item["review_sha256"],
            "reject",
            "integration-reviewer",
            "synthetic rejection preserves the identity",
        )
        self.assertEqual(rejected["status"], "rejected")
        self.connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
        resolved_plan = next(
            plan
            for plan in _list_review_plans_in_connection(self.connection)
            if plan["import_plan_id"] == str(ids["plan"])
        )
        self.assertEqual(resolved_plan["pending_count"], 0)
        self.assertEqual(resolved_plan["approved_count"], 1)
        self.assertEqual(resolved_plan["rejected_count"], 1)
        with self.assertRaisesRegex(PermissionError, "auditado"):
            _review_product_in_connection(
                self.connection,
                ids["plan"],
                ids["product"],
                fingerprint,
                "0" * 64,
                "approve",
                "integration-reviewer",
                "wrong retry evidence must fail",
            )
        reviewed_again = _review_product_in_connection(
            self.connection,
            ids["plan"],
            ids["product"],
            fingerprint,
            review_item["review_sha256"],
            "approve",
            "integration-reviewer",
            "synthetic review retry",
        )
        self.assertEqual(reviewed_again["status"], "already_approved")
        built = _build_release_in_connection(
            self.connection,
            ids["plan"],
            fingerprint,
            "2026.08.24-integration",
            "integration-publisher",
            "synthetic release build",
            brand_name="NATSUKI",
        )
        self.assertEqual(built["status"], "built")
        self.assertEqual(built["item_count"], 1)
        release_id = uuid.UUID(built["release_id"])
        rebuilt = _build_release_in_connection(
            self.connection,
            ids["plan"],
            fingerprint,
            "2026.08.24-integration",
            "integration-publisher",
            "synthetic release retry",
            brand_name="NATSUKI",
        )
        self.assertEqual(rebuilt["status"], "already_built")

        with self.assertRaisesRegex(PermissionError, "checksum"):
            _publish_release_in_connection(
                self.connection,
                release_id,
                "0" * 64,
                "integration-publisher",
                "wrong checksum must fail",
            )
        published = _publish_release_in_connection(
            self.connection,
            release_id,
            built["snapshot_sha256"],
            "integration-publisher",
            "synthetic publication",
        )
        self.assertEqual(published["status"], "published")
        self.assertEqual(
            _publish_release_in_connection(
                self.connection,
                release_id,
                built["snapshot_sha256"],
                "integration-publisher",
                "synthetic publication retry",
            )["status"],
            "already_published",
        )

        repository = ReleaseCatalogRepository.from_connection(self.connection, brand="NATSUKI")
        product = repository.product(str(ids["product"]))
        self.assertIsNotNone(product)
        self.assertNotIn("quantity_available", product["data"])
        self.assertEqual(product["identity_status"], "published_uuid")

        archived = _archive_release_in_connection(
            self.connection,
            release_id,
            built["snapshot_sha256"],
            "integration-publisher",
            "synthetic archive",
        )
        self.assertEqual(archived["status"], "archived")
        self.assertEqual(
            _archive_release_in_connection(
                self.connection,
                release_id,
                built["snapshot_sha256"],
                "integration-publisher",
                "synthetic archive retry",
            )["status"],
            "already_archived",
        )
        with self.assertRaises(FileNotFoundError):
            ReleaseCatalogRepository.from_connection(self.connection, brand="NATSUKI")

        self.connection.execute("RESET ROLE")
        release_audits = self.connection.execute(
            """
            SELECT event_type
            FROM perfect_catalog.audit_event
            WHERE entity_type='catalog_release' AND entity_id=%s
            ORDER BY occurred_at
            """,
            (release_id,),
        ).fetchall()
        self.assertEqual(
            [row[0] for row in release_audits],
            [
                "catalog_release.built",
                "catalog_release.published",
                "catalog_release.archived",
            ],
        )
        review_audits = self.connection.execute(
            """
            SELECT event_type, actor_type, actor_id,
                   metadata->>'review_evidence_sha256'
            FROM perfect_catalog.audit_event
            WHERE entity_type='product_template' AND entity_id=%s
              AND event_type='catalog_identity.approved'
            """,
            (ids["product"],),
        ).fetchall()
        self.assertEqual(
            review_audits,
            [
                (
                    "catalog_identity.approved",
                    "human",
                    "integration-reviewer",
                    review_item["review_sha256"],
                )
            ],
        )
        rejected_audits = self.connection.execute(
            """
            SELECT event_type, metadata->>'review_evidence_sha256'
            FROM perfect_catalog.audit_event
            WHERE entity_type='product_template' AND entity_id=%s
              AND event_type='catalog_identity.rejected'
            """,
            (ids["product_rejected"],),
        ).fetchall()
        self.assertEqual(
            rejected_audits,
            [
                (
                    "catalog_identity.rejected",
                    rejected_review_item["review_sha256"],
                )
            ],
        )

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
        definition = {
            "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
            "release_hash_algorithm": RELEASE_HASH_ALGORITHM,
            "source_kind": "applied_catalog",
            "source_plan_id": str(uuid.uuid4()),
            "source_plan_fingerprint_sha256": "c" * 64,
            "source_import_batch_id": str(ids["batch"]),
            "contract_version": "integration-contract",
            "rules_version": "integration-rules",
            "selection": {"brand": "NATSUKI"},
            "item_count": 1,
        }
        release_sha = release_snapshot_sha256(
            ids["brand"], "2026.08.24-test", definition, [item]
        )
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
                 snapshot_sha256)
            VALUES (%s,%s,'2026.08.24-test','draft',%s,%s,'integration-test',%s)
            """,
            (
                ids["release"],
                ids["brand"],
                Jsonb(definition),
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
        cursor.execute(
            """
            UPDATE perfect_catalog.catalog_release
            SET status='published', published_at=%s, published_by='integration-test'
            WHERE catalog_release_id=%s
            """,
            (now, ids["release"]),
        )

        self.connection.execute("SET ROLE perfect_catalog_app")
        repository = ReleaseCatalogRepository.from_connection(self.connection, brand="NATSUKI")
        self.assertEqual(repository.plan(), ("published:2026.08.24-test", 1, 1))
        results = repository.search("release", "Publicados", 10, 0)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], str(ids["product"]))
        self.assertEqual(results[0]["identity_status"], "published_uuid")
        self.assertNotIn("quantity_available", results[0]["data"])
        self.assertEqual(
            repository.categories(),
            [{"value": "Empaques / Publicados", "count": 1}],
        )
        self.assertIsNotNone(repository.product(str(ids["product"])))
        self.assertIsNone(repository.product("source-row:2"))

        self.connection.execute("RESET ROLE")
        with self.assertRaisesRegex(psycopg.errors.RaiseException, "append-only"):
            with self.connection.transaction():
                self.connection.execute(
                    """
                    UPDATE perfect_catalog.catalog_release_item
                    SET snapshot_data = snapshot_data || '{"name_original":"alterado"}'::jsonb
                    WHERE catalog_release_item_id=%s
                    """,
                    (ids["release_item"],),
                )
        with self.assertRaisesRegex(psycopg.errors.RaiseException, "invalid catalog_release"):
            with self.connection.transaction():
                self.connection.execute(
                    """
                    UPDATE perfect_catalog.catalog_release
                    SET status='published'
                    WHERE catalog_release_id=%s
                    """,
                    (ids["release"],),
                )


if __name__ == "__main__":
    unittest.main()
