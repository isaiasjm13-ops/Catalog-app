from __future__ import annotations

import io
import re
import unittest
import uuid
from typing import Any

import httpx
from PIL import Image

from perfect_catalog.public_generator_api import (
    PublicCatalogGateway,
    create_public_generator_app,
)

LINK_ID = uuid.uuid4()
VALID_TOKEN = "valid-token-abc123"


def _hidden_value(html: str, name: str) -> str:
    match = re.search(rf'name="{name}" value="([^"]*)"', html)
    assert match, f"no se encontró el campo oculto {name} en:\n{html}"
    return match.group(1)


def _png_bytes(color: tuple[int, int, int] = (10, 200, 30)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), color).save(buffer, format="PNG")
    return buffer.getvalue()


class SyntheticPublicCatalogGateway:
    """Gateway en memoria, sin Postgres — mismo espíritu que SyntheticReviewGateway
    en tests/test_operator_api.py: prueba la app FastAPI, no la base de datos real."""

    def __init__(self) -> None:
        self.links: dict[str, dict[str, Any]] = {
            VALID_TOKEN: {"public_catalog_link_id": str(LINK_ID), "label": "Proveedor de prueba"},
        }
        self.generations: list[dict[str, Any]] = []

    def resolve_link(self, token: str) -> dict[str, Any] | None:
        return self.links.get(token)

    def record_generation(self, **kwargs: Any) -> dict[str, Any]:
        self.generations.append(kwargs)
        return {"public_catalog_generation_id": str(uuid.uuid4())}


CSV_HEADERS = "Referencia interna,Nombre,Categoría de producto\n"


def _csv(rows: str) -> bytes:
    return (CSV_HEADERS + rows).encode("utf-8-sig")


class PublicGeneratorHttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.gateway = SyntheticPublicCatalogGateway()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_public_generator_app(self.gateway)),
            base_url="http://testserver",
            follow_redirects=False,
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def _get_form(self, token: str = VALID_TOKEN) -> tuple[str, str]:
        response = await self.client.get("/generar", params={"ref": token})
        self.assertEqual(response.status_code, 200)
        return response.text, _hidden_value(response.text, "csrf_token")

    def _multipart_files(self, *, excel: bytes, images: list[tuple[str, bytes]] = (), logo: bytes | None = None):
        files = [("odoo_file", ("productos.csv", excel, "text/csv"))]
        for filename, content in images:
            files.append(("images", (filename, content, "image/png")))
        if logo is not None:
            files.append(("logo", ("logo.png", logo, "image/png")))
        return files

    async def test_missing_ref_shows_friendly_error_not_a_form(self) -> None:
        response = await self.client.get("/generar")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Link no encontrado", response.text)

    async def test_unknown_token_is_rejected_like_a_missing_one(self) -> None:
        response = await self.client.get("/generar", params={"ref": "does-not-exist"})
        self.assertEqual(response.status_code, 404)

    async def test_valid_token_renders_form_with_link_label_and_sets_ticket_cookie(self) -> None:
        html, csrf = await self._get_form()
        self.assertIn("Proveedor de prueba", html)
        self.assertTrue(csrf)
        self.assertIn("pc_public_ticket", self.client.cookies)

    async def test_full_generation_downloads_html_and_records_who_generated_it(self) -> None:
        _, csrf = await self._get_form()
        excel = _csv('REF-1001,"Bomba de agua Toyota Corolla 2015",Bombas\n')
        response = await self.client.post(
            "/generar",
            data={
                "csrf_token": csrf,
                "declared_name": "Juan Pérez",
                "company_name": "Repuestos Andina",
                "brand_name": "Andina",
                "primary_color": "#0b6a53",
                "secondary_color": "#12355b",
            },
            files=self._multipart_files(excel=excel, images=[("REF-1001.png", _png_bytes())]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response.headers["content-disposition"])
        self.assertIn(b"Repuestos Andina", response.content)
        self.assertEqual(len(self.gateway.generations), 1)
        recorded = self.gateway.generations[0]
        self.assertEqual(recorded["declared_name"], "Juan Pérez")
        self.assertEqual(recorded["product_count"], 1)
        self.assertEqual(recorded["matched_image_count"], 1)
        self.assertEqual(str(recorded["link_id"]), str(LINK_ID))

    async def test_csrf_mismatch_between_cookie_and_field_is_rejected(self) -> None:
        await self._get_form()
        excel = _csv("REF-2002,Filtro,Filtros\n")
        response = await self.client.post(
            "/generar",
            data={
                "csrf_token": "not-the-real-ticket",
                "declared_name": "Alguien",
                "company_name": "Empresa",
                "brand_name": "Marca",
                "primary_color": "#0b6a53",
                "secondary_color": "#12355b",
            },
            files=self._multipart_files(excel=excel),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(self.gateway.generations), 0)

    async def test_revoked_link_between_get_and_post_is_rejected(self) -> None:
        _, csrf = await self._get_form()
        del self.gateway.links[VALID_TOKEN]
        excel = _csv("REF-3003,Bujía,Encendido\n")
        response = await self.client.post(
            "/generar",
            data={
                "csrf_token": csrf, "declared_name": "Alguien", "company_name": "Empresa",
                "brand_name": "Marca", "primary_color": "#0b6a53", "secondary_color": "#12355b",
            },
            files=self._multipart_files(excel=excel),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(self.gateway.generations), 0)

    async def test_missing_declared_name_is_rejected(self) -> None:
        _, csrf = await self._get_form()
        excel = _csv("REF-4004,Radiador,Enfriamiento\n")
        response = await self.client.post(
            "/generar",
            data={
                "csrf_token": csrf, "declared_name": "", "company_name": "Empresa",
                "brand_name": "Marca", "primary_color": "#0b6a53", "secondary_color": "#12355b",
            },
            files=self._multipart_files(excel=excel),
        )
        self.assertEqual(response.status_code, 400)

    async def test_link_rate_limit_blocks_after_threshold(self) -> None:
        app = create_public_generator_app(self.gateway, link_rate_limit=1, link_rate_window_seconds=3600.0)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver", follow_redirects=False,
        ) as client:
            first = await client.get("/generar", params={"ref": VALID_TOKEN})
            csrf = _hidden_value(first.text, "csrf_token")
            excel = _csv("REF-5005,Amortiguador,Suspensión\n")
            form_data = {
                "csrf_token": csrf, "declared_name": "Alguien", "company_name": "Empresa",
                "brand_name": "Marca", "primary_color": "#0b6a53", "secondary_color": "#12355b",
            }
            first_post = await client.post("/generar", data=form_data, files=self._multipart_files(excel=excel))
            self.assertEqual(first_post.status_code, 200)

            second = await client.get("/generar", params={"ref": VALID_TOKEN})
            csrf2 = _hidden_value(second.text, "csrf_token")
            form_data["csrf_token"] = csrf2
            second_post = await client.post("/generar", data=form_data, files=self._multipart_files(excel=excel))
            self.assertEqual(second_post.status_code, 400)
            self.assertIn("demasiados catálogos", second_post.text)


if __name__ == "__main__":
    unittest.main()
