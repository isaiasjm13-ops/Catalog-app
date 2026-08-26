from __future__ import annotations

import re
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


class SyntheticReviewGateway:
    def __init__(self) -> None:
        self.closed = False
        self.decisions: list[dict[str, Any]] = []
        self.intake_records: list[dict[str, Any]] = []
        self.promotions: list[dict[str, Any]] = []
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
        self.assertIn("frame-ancestors 'none'", dashboard.headers["content-security-policy"])
        queue = await self.client.get(f"/operator/plans/{PLAN_ID}?state=pending")
        self.assertIn("Empaque &lt;script&gt;incorrecto", queue.text)
        self.assertIn(REVIEW_SHA256, queue.text)
        self.assertNotIn("<script>incorrecto</script>", queue.text)

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
        self.assertEqual(OPERATOR_VERSION, "1.2.0")

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
