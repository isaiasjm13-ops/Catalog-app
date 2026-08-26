from __future__ import annotations

import hashlib
import re
import json
import tempfile
import unittest
import uuid
from pathlib import Path
from typing import Any

import httpx

from perfect_catalog.operator_api import (
    LOGIN_COOKIE_PATH,
    MAX_UPLOAD_REQUEST_BYTES,
    OPERATOR_VERSION,
    OperatorAuthenticator,
    create_operator_app,
)


PLAN_ID = uuid.uuid4()
PRODUCT_ID = uuid.uuid4()
FINGERPRINT = "a" * 64
REVIEW_SHA256 = "b" * 64
RELEASE_ID = uuid.uuid4()


class SyntheticReviewGateway:
    def __init__(self) -> None:
        self.closed = False
        self.decisions: list[dict[str, Any]] = []
        self.intake_records: list[dict[str, Any]] = []
        self.promotions: list[dict[str, Any]] = []
        self.image_indexes: list[dict[str, Any]] = []
        self.image_candidate_data: list[dict[str, Any]] = []
        self.catalog_exports: list[dict[str, Any]] = []
        self.release_changes: list[dict[str, Any]] = []
        self.release_data = [{
            "catalog_release_id": str(RELEASE_ID),
            "brand_id": str(uuid.uuid4()), "version": "2026.08", "status": "published",
            "snapshot_sha256": "c" * 64, "created_at": "2026-08-26T00:00:00Z",
            "created_by": "builder", "published_at": "2026-08-26T01:00:00Z",
            "published_by": "publisher", "item_count": 12,
        }]
        self.plan_data = {
            "import_plan_id": str(PLAN_ID),
            "approval_fingerprint_sha256": FINGERPRINT,
            "contract_version": "contract-test",
            "rules_version": "rules-test",
            "applied_at": "2026-08-24T00:00:00Z",
            "applied_by": "apply-reviewer",
            "original_name": "muestra <script>alert(1)</script>.xlsx",
            "candidate_count": 1,
            "pending_count": 1,
            "approved_count": 0,
            "rejected_count": 0,
            "inconsistent_count": 0,
        }

    def close(self) -> None:
        self.closed = True

    def plans(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return [self.plan_data]

    def plan(self, plan_id: uuid.UUID) -> dict[str, Any] | None:
        return self.plan_data if plan_id == PLAN_ID else None

    def page(
        self,
        plan_id: uuid.UUID,
        fingerprint: str,
        *,
        query: str = "",
        state: str = "all",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        if plan_id != PLAN_ID or fingerprint != FINGERPRINT:
            raise PermissionError("evidencia incorrecta")
        return {
            "plan_id": str(plan_id),
            "plan_status": "applied",
            "fingerprint": fingerprint,
            "candidate_count": 1,
            "filtered_count": 1,
            "limit": limit,
            "offset": offset,
            "query": query,
            "state": state,
            "items": [
                {
                    "product_id": str(PRODUCT_ID),
                    "identity_type": "product_template",
                    "name": "Empaque <script>incorrecto</script>",
                    "variant_name": None,
                    "reference": "ABC-001",
                    "catalog_status": "pending_review",
                    "reference_status": "pending",
                    "reference_count": 1,
                    "source_row_number": 2,
                    "review_state": "pending",
                    "review_sha256": REVIEW_SHA256,
                }
            ],
        }

    def decide(
        self,
        plan_id: uuid.UUID,
        product_id: uuid.UUID,
        fingerprint: str,
        review_sha256: str,
        decision: str,
        actor: str,
        reason: str,
    ) -> dict[str, Any]:
        self.decisions.append(
            {
                "plan_id": plan_id,
                "product_id": product_id,
                "fingerprint": fingerprint,
                "review_sha256": review_sha256,
                "decision": decision,
                "actor": actor,
                "reason": reason,
            }
        )
        return {"status": "approved" if decision == "approve" else "rejected"}

    def record_intake(self, record: dict[str, Any]) -> dict[str, Any]:
        stored = {
            **record,
            "intake_submission_id": str(record["intake_submission_id"]),
            "intake_asset_id": "asset-test" if record["validation_status"] == "quarantined" else None,
            "duplicate_content": False,
            "intake_promotion_id": None,
            "import_plan_id": None,
            "promoted_at": None,
            "promoted_by": None,
            "image_archive_index_id": None,
            "image_index_sha256": None,
            "image_count": None,
            "ambiguous_count": None,
            "indexed_at": None,
            "indexed_by": None,
        }
        self.intake_records.append(stored)
        return stored

    def promote_intake(
        self, submission_id: uuid.UUID, intake_root: Path, output_dir: Path,
        actor: str, reason: str, max_rows: int,
    ) -> dict[str, Any]:
        record = next(
            (item for item in self.intake_records if item["intake_submission_id"] == str(submission_id)),
            None,
        )
        if record is None or record["intake_kind"] != "odoo_data" or record["validation_status"] != "quarantined":
            raise PermissionError("ingreso no promovible")
        if record["intake_promotion_id"]:
            return {"status": "already_promoted"}
        promotion = {
            "submission_id": submission_id, "intake_root": intake_root,
            "output_dir": output_dir, "actor": actor, "reason": reason,
            "max_rows": max_rows,
        }
        self.promotions.append(promotion)
        record["intake_promotion_id"] = str(uuid.uuid4())
        record["import_plan_id"] = str(uuid.uuid4())
        return {"status": "promoted"}

    def index_image_archive(
        self, submission_id: uuid.UUID, intake_root: Path, actor: str, reason: str,
    ) -> dict[str, Any]:
        record = next(item for item in self.intake_records if item["intake_submission_id"] == str(submission_id))
        if record["intake_kind"] != "image_archive" or record["validation_status"] != "quarantined":
            raise PermissionError("ingreso no indexable")
        if record["image_archive_index_id"]:
            return {"status": "already_indexed"}
        record.update({
            "image_archive_index_id": str(uuid.uuid4()), "image_index_sha256": "f" * 64,
            "image_count": 2, "ambiguous_count": 1, "indexed_by": actor,
        })
        self.image_indexes.append({"submission_id": submission_id, "intake_root": intake_root, "actor": actor, "reason": reason})
        return {"status": "indexed"}

    def generate_image_candidates(
        self, image_archive_index_id: uuid.UUID, actor: str, reason: str,
    ) -> dict[str, Any]:
        if not self.image_candidate_data:
            self.image_candidate_data.append({
                "image_product_candidate_id": str(uuid.uuid4()), "evidence_sha256": "9" * 64,
                "confidence": 1, "original_filename": "NK-001.jpg", "member_path": "fotos/NK-001.jpg",
                "lookup_key": "NK-001", "content_sha256": "8" * 64, "reference": "NK-001",
                "product_name": "Empaque <seguro>", "product_template_id": str(uuid.uuid4()),
                "product_variant_id": None, "decision": None, "decided_by": None, "decided_at": None,
                "approved_image_materialization_id": None, "storage_relpath": None,
            })
        return {"status": "generated", "candidate_count": 1, "inserted_count": 1}

    def image_candidates(self, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        return {"items": self.image_candidate_data[offset:offset + limit],
                "filtered_count": len(self.image_candidate_data), "limit": limit, "offset": offset}

    def decide_image_candidate(
        self, candidate_id: uuid.UUID, evidence_sha256: str, decision: str,
        actor: str, reason: str,
    ) -> dict[str, Any]:
        candidate = next(item for item in self.image_candidate_data if item["image_product_candidate_id"] == str(candidate_id))
        if candidate["evidence_sha256"] != evidence_sha256:
            raise PermissionError("evidencia incorrecta")
        candidate.update({"decision": decision, "decided_by": actor, "decided_at": "2026-08-26"})
        return {"status": decision}

    def materialize_approved_image(
        self, candidate_id: uuid.UUID, evidence_sha256: str,
        intake_root: Path, image_root: Path, actor: str, reason: str,
    ) -> dict[str, Any]:
        candidate = next(item for item in self.image_candidate_data if item["image_product_candidate_id"] == str(candidate_id))
        if candidate["decision"] != "approved" or candidate["evidence_sha256"] != evidence_sha256:
            raise PermissionError("no aprobado")
        candidate["approved_image_materialization_id"] = str(uuid.uuid4())
        candidate["storage_relpath"] = "objects/88/" + "8" * 64 + ".jpg"
        return {"status": "materialized"}

    def intake_submissions(
        self,
        *,
        kind: str = "all",
        status: str = "all",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        items = list(reversed(self.intake_records))
        if kind != "all":
            items = [item for item in items if item["intake_kind"] == kind]
        if status != "all":
            items = [item for item in items if item["validation_status"] == status]
        return {
            "items": items[offset : offset + limit],
            "filtered_count": len(items),
            "kind": kind,
            "status": status,
            "limit": limit,
            "offset": offset,
        }

    def catalog_releases(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return self.release_data[:limit]

    def build_catalog_release(
        self, plan_id: uuid.UUID, fingerprint: str, version: str,
        actor: str, reason: str, brand: str,
    ) -> dict[str, Any]:
        release_id = uuid.uuid4()
        change = {"operation": "build", "plan_id": plan_id, "fingerprint": fingerprint,
                  "version": version, "actor": actor, "reason": reason, "brand": brand,
                  "release_id": release_id}
        self.release_changes.append(change)
        self.release_data.insert(0, {
            "catalog_release_id": str(release_id), "brand_id": str(uuid.uuid4()),
            "version": version, "status": "draft", "snapshot_sha256": "e" * 64,
            "created_at": "2026-08-26T02:00:00Z", "created_by": actor,
            "published_at": None, "published_by": None, "item_count": 1,
        })
        return {"status": "built", "release_id": str(release_id)}

    def publish_catalog_release(
        self, release_id: uuid.UUID, snapshot_sha256: str, actor: str, reason: str,
    ) -> dict[str, Any]:
        release = next(item for item in self.release_data if item["catalog_release_id"] == str(release_id))
        if release["snapshot_sha256"] != snapshot_sha256:
            raise PermissionError("checksum incorrecto")
        release["status"] = "published"
        release["published_by"] = actor
        self.release_changes.append({"operation": "publish", "release_id": release_id, "actor": actor, "reason": reason})
        return {"status": "published", "release_id": str(release_id)}

    def preview_catalog_release(
        self, release_id: uuid.UUID, *, group_by: str, group_by_secondary: str = "",
        filter_field: str = "all", filter_query: str = "", sample_limit: int = 24,
    ) -> dict[str, Any]:
        return {
            "release": {"release_id": str(release_id), "version": "2026.08", "status": "published",
                        "snapshot_sha256": "c" * 64, "item_count": 12},
            "group_by": group_by, "group_by_secondary": group_by_secondary,
            "filter_field": filter_field, "filter_query": filter_query,
            "source_count": 12, "total_count": 12, "sample_count": 1,
            "groups": [{"label": "Motor <seguro>", "count": 12, "products": [{
                "internal_reference_original": "NK-001", "name_original": "Empaque <script>",
                "category_path": "Motor", "brand": "Natsuki",
                "oem_references": ["OEM-123"], "applications": ["Toyota Corolla"],
            }]}],
        }

    def catalog_preview_image(
        self, release_id: uuid.UUID, item_number: int, image_root: Path,
    ) -> Path:
        if item_number != 1:
            raise FileNotFoundError
        return Path(__file__)

    def export_catalog(
        self, release_id: uuid.UUID, output_root: Path,
        *, formats: tuple[str, ...], export_config: dict[str, Any],
        image_root: Path | None = None,
    ) -> dict[str, Any]:
        export_id = uuid.uuid4()
        directory = output_root / str(release_id) / str(export_id)
        directory.mkdir(parents=True)
        files = []
        for output_format in formats:
            filename = f"catalog.{output_format.replace('indesign-json', 'indesign.json')}"
            content = f"synthetic-{output_format}".encode()
            (directory / filename).write_bytes(content)
            files.append({
                "format": output_format,
                "filename": filename,
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            })
        manifest_name = "catalog.manifest.json"
        manifest = {
            "schema": "perfect-catalog.export-manifest.v1",
            "release": {"release_id": str(release_id), "version": "2026.08", "item_count": 12},
            "files": files,
        }
        (directory / manifest_name).write_text(json.dumps(manifest), encoding="utf-8")
        result = {**manifest, "export_id": str(export_id), "manifest": manifest_name}
        self.catalog_exports.append({"config": export_config, "formats": formats, **result})
        return result


def hidden_value(html: str, name: str) -> str:
    match = re.search(
        rf'<input[^>]+name="{re.escape(name)}"[^>]+value="([^"]*)"', html
    )
    if match is None:
        raise AssertionError(f"No se encontró el campo oculto {name!r}.")
    return match.group(1)


class OperatorAuthenticatorTests(unittest.TestCase):
    def test_session_is_signed_revocable_and_expires(self) -> None:
        clock = [1_000.0]
        auth = OperatorAuthenticator(
            "qa-user",
            "temporary-123",
            session_ttl_seconds=60,
            now=lambda: clock[0],
            pbkdf2_iterations=1,
        )
        self.assertTrue(auth.authenticate("temporary-123"))
        self.assertFalse(auth.authenticate("wrong-password"))
        session, cookie = auth.create_session()
        self.assertEqual(auth.get_session(cookie), session)
        self.assertIsNone(auth.get_session(cookie + "tampered"))
        auth.revoke(cookie)
        self.assertIsNone(auth.get_session(cookie))
        session, cookie = auth.create_session()
        clock[0] += 60
        self.assertIsNone(auth.get_session(cookie))

    def test_access_code_and_actor_require_safe_minimums(self) -> None:
        with self.assertRaisesRegex(ValueError, "12 caracteres"):
            OperatorAuthenticator("qa", "short", pbkdf2_iterations=1)
        with self.assertRaisesRegex(ValueError, "actor"):
            OperatorAuthenticator("", "temporary-123", pbkdf2_iterations=1)

    def test_authentication_distinguishes_bad_code_from_rate_limit(self) -> None:
        auth = OperatorAuthenticator("qa", "temporary-123", pbkdf2_iterations=1)
        for _ in range(5):
            self.assertEqual(auth.authenticate_result("wrong-password"), "invalid_code")
        self.assertEqual(auth.authenticate_result("temporary-123"), "rate_limited")


class OperatorHttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.gateway = SyntheticReviewGateway()
        self.auth = OperatorAuthenticator(
            "web-reviewer",
            "temporary-123",
            pbkdf2_iterations=1,
        )
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(
                app=create_operator_app(
                    self.gateway,
                    self.auth,
                    intake_root=Path(self.temporary.name),
                    catalog_output_dir=Path(self.temporary.name) / "catalogs",
                )
            ),
            base_url="http://testserver",
            follow_redirects=False,
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        self.temporary.cleanup()

    async def login(self) -> None:
        login_page = await self.client.get("/operator/login")
        csrf = hidden_value(login_page.text, "csrf_token")
        response = await self.client.post(
            "/operator/login",
            data={"csrf_token": csrf, "access_code": "temporary-123"},
            headers={"Origin": "http://testserver"},
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/operator")

    async def test_login_is_required_and_wrong_code_is_rejected(self) -> None:
        response = await self.client.get("/operator")
        self.assertEqual(response.status_code, 303)
        login_page = await self.client.get("/operator/login")
        csrf = hidden_value(login_page.text, "csrf_token")
        rejected = await self.client.post(
            "/operator/login",
            data={"csrf_token": csrf, "access_code": "incorrect-code"},
            headers={"Origin": "http://testserver"},
        )
        self.assertEqual(rejected.status_code, 401)
        self.assertIn("código temporal no coincide", rejected.text)
        self.assertNotIn("pc_operator_session", rejected.headers.get("set-cookie", ""))

        malformed_origin = await self.client.post(
            "/operator/login",
            data={"csrf_token": csrf, "access_code": "temporary-123"},
            headers={"Origin": "http://testserver:invalid"},
        )
        self.assertEqual(malformed_origin.status_code, 401)
        self.assertIn("Origen local no verificado", malformed_origin.text)

    async def test_login_challenge_cookie_scope_and_missing_cookie_diagnostic(self) -> None:
        login_page = await self.client.get("/operator/login")
        csrf = hidden_value(login_page.text, "csrf_token")
        self.assertIn(f"Path={LOGIN_COOKIE_PATH}", login_page.headers.get("set-cookie", ""))
        self.assertIn("HttpOnly", login_page.headers.get("set-cookie", ""))
        self.client.cookies.delete("pc_operator_login")
        response = await self.client.post(
            "/operator/login",
            data={"csrf_token": csrf, "access_code": "temporary-123"},
            headers={"Origin": "http://testserver"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("cookie de challenge no disponible", response.text)

    async def test_same_origin_referer_fallback_requires_fetch_metadata(self) -> None:
        page = await self.client.get("/operator/login")
        csrf = hidden_value(page.text, "csrf_token")
        response = await self.client.post(
            "/operator/login",
            data={"csrf_token": csrf, "access_code": "temporary-123"},
            headers={
                "Referer": "http://testserver/operator/login",
                "Sec-Fetch-Site": "same-origin",
            },
        )
        self.assertEqual(response.status_code, 303)

    async def test_operator_pages_escape_source_text_and_set_security_headers(self) -> None:
        await self.login()
        dashboard = await self.client.get("/operator")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("muestra &lt;script&gt;", dashboard.text)
        self.assertNotIn("<script>alert(1)</script>", dashboard.text)
        self.assertEqual(dashboard.headers["cache-control"], "no-store")
        self.assertEqual(dashboard.headers["referrer-policy"], "same-origin")
        self.assertIn("frame-ancestors 'none'", dashboard.headers["content-security-policy"])
        queue = await self.client.get(f"/operator/plans/{PLAN_ID}?state=pending")
        self.assertIn("Empaque &lt;script&gt;incorrecto", queue.text)
        self.assertIn(REVIEW_SHA256, queue.text)
        self.assertNotIn("<script>incorrecto</script>", queue.text)

    async def test_catalog_workspace_exports_and_downloads_manifest_files(self) -> None:
        await self.login()
        page = await self.client.get("/operator/catalogs")
        self.assertEqual(page.status_code, 200)
        self.assertIn("2026.08", page.text)
        self.assertIn("12 productos", page.text)
        self.assertIn('name="selected_references"', page.text)
        response = await self.client.post(
            f"/operator/catalogs/{RELEASE_ID}/exports",
            data={
                "csrf_token": hidden_value(page.text, "csrf_token"),
                "title": "Catálogo web",
                "subtitle": "Edición segura",
                "group_by": "category_path",
                "group_by_secondary": "brand",
                "filter_field": "all",
                "filter_query": "",
                "selected_references": "NK-001\nNK-002",
                "theme": "industrial",
                "columns": "2",
                "format_html": "yes",
                "format_pdf": "yes",
                "format_pptx": "no",
                "format_indesign_json": "yes",
                "template_profile": "T4",
                "confirm": "yes",
            },
            headers={"Origin": "http://testserver"},
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/operator/catalogs?result=created")
        self.assertEqual(self.gateway.catalog_exports[0]["formats"], ("html", "pdf", "indesign-json"))
        self.assertEqual(
            self.gateway.catalog_exports[0]["config"]["selected_references"],
            "NK-001\nNK-002",
        )
        export_id = self.gateway.catalog_exports[0]["export_id"]
        download = await self.client.get(
            f"/operator/catalogs/{RELEASE_ID}/exports/{export_id}/catalog.pdf"
        )
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.content, b"synthetic-pdf")
        pdf_path = Path(self.temporary.name) / "catalogs" / str(RELEASE_ID) / export_id / "catalog.pdf"
        pdf_path.write_bytes(b"archivo manipulado")
        tampered = await self.client.get(
            f"/operator/catalogs/{RELEASE_ID}/exports/{export_id}/catalog.pdf"
        )
        self.assertEqual(tampered.status_code, 404)
        denied = await self.client.get(
            f"/operator/catalogs/{RELEASE_ID}/exports/{export_id}/secret.txt"
        )
        self.assertEqual(denied.status_code, 404)

    async def test_catalog_export_requires_origin_csrf_and_exact_fields(self) -> None:
        await self.login()
        page = await self.client.get("/operator/catalogs")
        self.assertIn("Estado del estudio editorial", page.text)
        self.assertIn("Entregables con integridad comprobada", page.text)
        self.assertIn("01 · Estructura del contenido", page.text)
        self.assertIn('name="theme" value="industrial" aria-label="Industrial · repuestos"', page.text)
        self.assertIn('type="radio" name="template_profile" value="TABLE"', page.text)
        self.assertIn('<label><span>Tema</span><select name="theme">', page.text)
        fields = {
            "csrf_token": hidden_value(page.text, "csrf_token"),
            "title": "Catálogo web", "subtitle": "", "group_by": "category_path",
            "group_by_secondary": "", "filter_field": "all", "filter_query": "",
            "selected_references": "",
            "theme": "forest",
            "columns": "2", "format_pdf": "yes", "format_pptx": "yes",
            "format_html": "yes",
            "format_indesign_json": "yes", "confirm": "yes",
            "template_profile": "TABLE",
        }
        no_origin = await self.client.post(f"/operator/catalogs/{RELEASE_ID}/exports", data=fields)
        self.assertEqual(no_origin.status_code, 403)
        bad_csrf = await self.client.post(
            f"/operator/catalogs/{RELEASE_ID}/exports",
            data={**fields, "csrf_token": "wrong"}, headers={"Origin": "http://testserver"},
        )
        self.assertEqual(bad_csrf.status_code, 403)
        self.assertFalse(self.gateway.catalog_exports)

    async def test_catalog_release_build_and_publish_are_individual_csrf_posts(self) -> None:
        await self.login()
        page = await self.client.get("/operator/catalogs")
        csrf = hidden_value(page.text, "csrf_token")
        built = await self.client.post(
            "/operator/catalogs/releases",
            data={
                "csrf_token": csrf, "plan_id": str(PLAN_ID), "fingerprint": FINGERPRINT,
                "version": "2026.09", "brand": "NATSUKI", "reason": "Edición revisada",
                "confirm": "yes",
            }, headers={"Origin": "http://testserver"},
        )
        self.assertEqual(built.status_code, 303)
        self.assertEqual(built.headers["location"], "/operator/catalogs?result=built")
        draft = self.gateway.release_data[0]
        published = await self.client.post(
            f"/operator/catalogs/{draft['catalog_release_id']}/publish",
            data={
                "csrf_token": csrf, "snapshot_sha256": draft["snapshot_sha256"],
                "reason": "Checksum revisado", "confirm": "yes",
            }, headers={"Origin": "http://testserver"},
        )
        self.assertEqual(published.status_code, 303)
        self.assertEqual(published.headers["location"], "/operator/catalogs?result=published")
        self.assertEqual(draft["status"], "published")
        self.assertEqual([item["operation"] for item in self.gateway.release_changes], ["build", "publish"])

    async def test_catalog_preview_is_read_only_limited_and_escaped(self) -> None:
        await self.login()
        response = await self.client.get(
            f"/operator/catalogs/{RELEASE_ID}/preview?group_by=category_path&columns=3&theme=industrial"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Muestra 1 de 12 productos seleccionados", response.text)
        self.assertIn("columns-3", response.text)
        self.assertIn("theme-industrial", response.text)
        self.assertIn("Motor &lt;seguro&gt;", response.text)
        self.assertNotIn("<script>", response.text)
        self.assertIn("Motor · Natsuki", response.text)
        self.assertIn("<b>OEM:</b> OEM-123", response.text)
        self.assertIn("<b>Aplicaciones:</b> Toyota Corolla", response.text)
        image = await self.client.get(
            f"/operator/catalogs/{RELEASE_ID}/preview/images/1"
        )
        self.assertEqual(image.status_code, 200)
        missing_image = await self.client.get(
            f"/operator/catalogs/{RELEASE_ID}/preview/images/2"
        )
        self.assertEqual(missing_image.status_code, 404)
        invalid = await self.client.get(
            f"/operator/catalogs/{RELEASE_ID}/preview?group_by=unknown&columns=2"
        )
        self.assertEqual(invalid.status_code, 400)
        invalid_theme = await self.client.get(
            f"/operator/catalogs/{RELEASE_ID}/preview?theme=custom"
        )
        self.assertEqual(invalid_theme.status_code, 400)
        indesign = await self.client.get(
            f"/operator/catalogs/{RELEASE_ID}/preview?preview_target=indesign&template_profile=TABLE"
        )
        self.assertEqual(indesign.status_code, 200)
        self.assertIn("target-indesign profile-TABLE", indesign.text)
        self.assertIn("Vista InDesign TABLE", indesign.text)
        self.assertIn("Páginas estimadas", indesign.text)
        self.assertIn("Portada · página 1", indesign.text)
        self.assertIn("12 productos · separador", indesign.text)
        invalid_profile = await self.client.get(
            f"/operator/catalogs/{RELEASE_ID}/preview?preview_target=indesign&template_profile=T8"
        )
        self.assertEqual(invalid_profile.status_code, 400)

    async def test_decision_requires_same_origin_and_exact_csrf(self) -> None:
        await self.login()
        queue = await self.client.get(f"/operator/plans/{PLAN_ID}?state=pending")
        csrf = hidden_value(queue.text, "csrf_token")
        form = {
            "csrf_token": csrf,
            "fingerprint": FINGERPRINT,
            "review_sha256": REVIEW_SHA256,
            "decision": "approve",
            "reason": "Nombre y referencia verificados",
            "confirm": "yes",
        }
        rejected = await self.client.post(
            f"/operator/plans/{PLAN_ID}/products/{PRODUCT_ID}/decision",
            data={**form, "csrf_token": "wrong"},
            headers={"Origin": "http://testserver"},
        )
        self.assertEqual(rejected.status_code, 403)
        missing_origin = await self.client.post(
            f"/operator/plans/{PLAN_ID}/products/{PRODUCT_ID}/decision",
            data=form,
        )
        self.assertEqual(missing_origin.status_code, 403)
        self.assertEqual(self.gateway.decisions, [])

        unconfirmed = await self.client.post(
            f"/operator/plans/{PLAN_ID}/products/{PRODUCT_ID}/decision",
            data={key: value for key, value in form.items() if key != "confirm"},
            headers={"Origin": "http://testserver"},
        )
        self.assertEqual(unconfirmed.status_code, 409)
        self.assertEqual(self.gateway.decisions, [])

        too_short = await self.client.post(
            f"/operator/plans/{PLAN_ID}/products/{PRODUCT_ID}/decision",
            data={**form, "reason": "no"},
            headers={"Origin": "http://testserver"},
        )
        self.assertEqual(too_short.status_code, 409)
        self.assertEqual(self.gateway.decisions, [])

        accepted = await self.client.post(
            f"/operator/plans/{PLAN_ID}/products/{PRODUCT_ID}/decision",
            data=form,
            headers={"Origin": "http://testserver"},
        )
        self.assertEqual(accepted.status_code, 303)
        self.assertIn("result=approved", accepted.headers["location"])
        self.assertEqual(len(self.gateway.decisions), 1)
        self.assertEqual(self.gateway.decisions[0]["actor"], "web-reviewer")
        self.assertEqual(
            self.gateway.decisions[0]["reason"],
            "Nombre y referencia verificados",
        )

    async def test_get_never_exposes_a_decision_route(self) -> None:
        await self.login()
        response = await self.client.get(
            f"/operator/plans/{PLAN_ID}/products/{PRODUCT_ID}/decision"
        )
        self.assertEqual(response.status_code, 405)
        self.assertEqual(self.gateway.decisions, [])

    async def test_openapi_and_public_catalog_are_not_mounted(self) -> None:
        await self.login()
        self.assertEqual((await self.client.get("/openapi.json")).status_code, 404)
        self.assertEqual((await self.client.get("/api/v1/products")).status_code, 404)
        self.assertEqual(OPERATOR_VERSION, "1.5.0")

    async def test_promotion_requires_individual_post_origin_csrf_and_confirmation(self) -> None:
        await self.login()
        page = await self.client.get("/operator/intake")
        csrf = hidden_value(page.text, "csrf_token")
        uploaded = await self.client.post(
            "/operator/intake",
            data={
                "csrf_token": csrf, "kind": "odoo_data",
                "reason": "Exportación sintética para dry-run", "confirm": "yes",
            },
            files={"file": ("productos.csv", b"Nombre,Referencia interna\nEmpaque,ABC-1\n", "text/csv")},
            headers={"Origin": "http://testserver"},
        )
        self.assertEqual(uploaded.status_code, 303)
        submission_id = self.gateway.intake_records[-1]["intake_submission_id"]
        form = {
            "csrf_token": csrf,
            "reason": "Perfilado individual autorizado por calidad",
            "confirm": "yes",
        }
        path = f"/operator/intake/{submission_id}/promote"
        self.assertEqual((await self.client.get(path)).status_code, 405)
        self.assertEqual((await self.client.post(path, data=form)).status_code, 403)
        self.assertEqual((await self.client.post(
            path, data={**form, "csrf_token": "wrong"}, headers={"Origin": "http://testserver"}
        )).status_code, 403)
        self.assertEqual((await self.client.post(
            path, data={key: value for key, value in form.items() if key != "confirm"},
            headers={"Origin": "http://testserver"},
        )).status_code, 409)
        self.assertEqual(self.gateway.promotions, [])
        accepted = await self.client.post(path, data=form, headers={"Origin": "http://testserver"})
        self.assertEqual(accepted.status_code, 303)
        self.assertIn("result=promoted", accepted.headers["location"])
        self.assertEqual(len(self.gateway.promotions), 1)
        self.assertEqual(self.gateway.promotions[0]["actor"], "web-reviewer")
        self.assertEqual(self.gateway.promotions[0]["max_rows"], 5_000)
        history = await self.client.get("/operator/intake")
        self.assertIn("Dry-run creado", history.text)
        self.assertNotIn("Promover a dry-run", history.text)

    async def test_image_archive_index_is_individual_and_never_extracts_from_route(self) -> None:
        await self.login()
        page = await self.client.get("/operator/intake")
        csrf = hidden_value(page.text, "csrf_token")
        submission_id = str(uuid.uuid4())
        self.gateway.intake_records.append({
            "intake_submission_id": submission_id, "intake_asset_id": "asset", "intake_kind": "image_archive",
            "original_name": "imagenes.zip", "extension": ".zip", "claimed_media_type": "application/zip",
            "detected_media_type": "application/zip", "size_bytes": 100, "sha256": "a" * 64,
            "validation_status": "quarantined", "duplicate_content": False, "validation_report": {"image_files": 2},
            "submitted_by": "web-reviewer", "reason": "Paquete de imágenes", "submitted_at": "2026-08-26",
            "intake_promotion_id": None, "import_plan_id": None, "promoted_at": None, "promoted_by": None,
            "image_archive_index_id": None, "image_index_sha256": None, "image_count": None,
            "ambiguous_count": None, "indexed_at": None, "indexed_by": None,
        })
        path = f"/operator/intake/{submission_id}/index-images"
        form = {"csrf_token": csrf, "reason": "Índice autorizado", "confirm": "yes"}
        self.assertEqual((await self.client.post(path, data=form)).status_code, 403)
        accepted = await self.client.post(path, data=form, headers={"Origin": "http://testserver"})
        self.assertEqual(accepted.status_code, 303)
        self.assertIn("result=indexed", accepted.headers["location"])
        self.assertEqual(self.gateway.image_indexes[0]["actor"], "web-reviewer")
        history = await self.client.get("/operator/intake")
        self.assertIn("2 imágenes indexadas", history.text)
        self.assertIn("1 ambiguas", history.text)

    async def test_image_candidate_generation_and_decision_are_separate_posts(self) -> None:
        await self.login()
        page = await self.client.get("/operator/images")
        self.assertEqual(page.status_code, 200)
        csrf = hidden_value(page.text, "csrf_token") if 'name="csrf_token"' in page.text else hidden_value((await self.client.get("/operator/intake")).text, "csrf_token")
        generated = await self.client.post(
            f"/operator/images/index/{uuid.uuid4()}/candidates",
            data={"csrf_token": csrf, "reason": "Cruce exacto revisable", "confirm": "yes"},
            headers={"Origin": "http://testserver"},
        )
        self.assertEqual(generated.status_code, 303)
        queue = await self.client.get("/operator/images")
        self.assertIn("NK-001.jpg", queue.text)
        self.assertIn("Empaque &lt;seguro&gt;", queue.text)
        candidate = self.gateway.image_candidate_data[0]
        decided = await self.client.post(
            f"/operator/images/candidates/{candidate['image_product_candidate_id']}/decision",
            data={"csrf_token": csrf, "evidence_sha256": candidate["evidence_sha256"],
                  "decision": "approved", "reason": "Fotografía confirmada", "confirm": "yes"},
            headers={"Origin": "http://testserver"},
        )
        self.assertEqual(decided.status_code, 303)
        self.assertIn("result=approved", decided.headers["location"])
        self.assertEqual(candidate["decision"], "approved")
        materialized = await self.client.post(
            f"/operator/images/candidates/{candidate['image_product_candidate_id']}/materialize",
            data={"csrf_token": csrf, "evidence_sha256": candidate["evidence_sha256"],
                  "reason": "Copia primaria autorizada", "confirm": "yes"},
            headers={"Origin": "http://testserver"},
        )
        self.assertEqual(materialized.status_code, 303)
        self.assertIn("result=materialized", materialized.headers["location"])
        self.assertTrue(candidate["storage_relpath"].startswith("objects/"))

    async def test_intake_requires_auth_origin_csrf_and_confirmation(self) -> None:
        unauthenticated = await self.client.get("/operator/intake")
        self.assertEqual(unauthenticated.status_code, 303)
        await self.login()
        page = await self.client.get("/operator/intake")
        csrf = hidden_value(page.text, "csrf_token")
        files = {"file": ("manual.pdf", b"%PDF-1.7\nvalid", "application/pdf")}
        fields = {
            "csrf_token": csrf,
            "kind": "manual_pdf",
            "reason": "Manual oficial recibido",
            "confirm": "yes",
        }
        missing_origin = await self.client.post("/operator/intake", data=fields, files=files)
        self.assertEqual(missing_origin.status_code, 403)
        wrong_csrf = await self.client.post(
            "/operator/intake",
            data={**fields, "csrf_token": "wrong"},
            files=files,
            headers={"Origin": "http://testserver"},
        )
        self.assertEqual(wrong_csrf.status_code, 403)
        unconfirmed = await self.client.post(
            "/operator/intake",
            data={key: value for key, value in fields.items() if key != "confirm"},
            files=files,
            headers={"Origin": "http://testserver"},
        )
        self.assertEqual(unconfirmed.status_code, 422)
        self.assertEqual(self.gateway.intake_records, [])

        duplicated = await self.client.post(
            "/operator/intake",
            files=[
                ("csrf_token", (None, csrf)),
                ("kind", (None, "manual_pdf")),
                ("kind", (None, "odoo_data")),
                ("reason", (None, "Carga con parámetro duplicado")),
                ("confirm", (None, "yes")),
                ("file", ("manual.pdf", b"%PDF-1.7\nvalid", "application/pdf")),
            ],
            headers={"Origin": "http://testserver"},
        )
        self.assertEqual(duplicated.status_code, 422)
        self.assertEqual(self.gateway.intake_records, [])

        oversized = await self.client.post(
            "/operator/intake",
            content=b"ignored",
            headers={
                "Origin": "http://testserver",
                "Content-Type": "multipart/form-data; boundary=test",
                "Content-Length": str(MAX_UPLOAD_REQUEST_BYTES + 1),
            },
        )
        self.assertEqual(oversized.status_code, 413)

    async def test_intake_quarantines_valid_file_and_records_rejection(self) -> None:
        await self.login()
        page = await self.client.get("/operator/intake")
        csrf = hidden_value(page.text, "csrf_token")
        fields = {
            "csrf_token": csrf,
            "kind": "manual_pdf",
            "reason": "Manual oficial recibido",
            "confirm": "yes",
        }
        accepted = await self.client.post(
            "/operator/intake",
            data=fields,
            files={"file": ("manual<script>.pdf", b"%PDF-1.7\nvalid", "application/pdf")},
            headers={"Origin": "http://testserver"},
        )
        self.assertEqual(accepted.status_code, 303)
        self.assertIn("result=quarantined", accepted.headers["location"])
        self.assertEqual(self.gateway.intake_records[0]["submitted_by"], "web-reviewer")

        rejected = await self.client.post(
            "/operator/intake",
            data=fields,
            files={"file": ("manual.pdf", b"not-pdf", "application/pdf")},
            headers={"Origin": "http://testserver"},
        )
        self.assertEqual(rejected.status_code, 303)
        self.assertIn("result=rejected", rejected.headers["location"])
        history = await self.client.get("/operator/intake?result=rejected")
        self.assertIn("Archivo rechazado", history.text)
        self.assertIn("Manual oficial recibido", history.text)
        self.assertIn("manual&lt;script&gt;.pdf", history.text)
        self.assertNotIn("manual<script>.pdf", history.text)
        self.assertEqual(len(self.gateway.intake_records), 2)

        invalid_filter = await self.client.get("/operator/intake?kind=executable")
        self.assertEqual(invalid_filter.status_code, 400)


if __name__ == "__main__":
    unittest.main()
