from __future__ import annotations

import re
import unittest
import uuid
from typing import Any

import httpx

from perfect_catalog.operator_api import (
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


class OperatorHttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.gateway = SyntheticReviewGateway()
        self.auth = OperatorAuthenticator(
            "web-reviewer",
            "temporary-123",
            pbkdf2_iterations=1,
        )
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(
                app=create_operator_app(self.gateway, self.auth)
            ),
            base_url="http://testserver",
            follow_redirects=False,
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

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
        self.assertNotIn("pc_operator_session", rejected.headers.get("set-cookie", ""))

        malformed_origin = await self.client.post(
            "/operator/login",
            data={"csrf_token": csrf, "access_code": "temporary-123"},
            headers={"Origin": "http://testserver:invalid"},
        )
        self.assertEqual(malformed_origin.status_code, 401)

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
        self.assertEqual(OPERATOR_VERSION, "1.0.0")


if __name__ == "__main__":
    unittest.main()
