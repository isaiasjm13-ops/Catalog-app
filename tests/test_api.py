from __future__ import annotations

import unittest
from typing import Any

import httpx

from perfect_catalog.api import create_app


class SyntheticCatalogRepository:
    def __init__(self) -> None:
        self.closed = False
        self.rows = [
            {
                "row": 2,
                "data": {
                    "internal_reference_original": "001-A-00",
                    "internal_reference_normalized": "001-A-00",
                    "name_original": "EMPAQUE SINTÉTICO ÁRBOL",
                    "name_normalized": "EMPAQUE SINTÉTICO ÁRBOL",
                    "category_path": "Todos / Empaques",
                    "quantity_available": 0,
                    "image_status": "absent",
                    "brand": "NATSUKI",
                    "family": "empaques",
                },
            },
            {
                "row": 3,
                "data": {
                    "internal_reference_original": "002-B-00",
                    "internal_reference_normalized": "002-B-00",
                    "name_original": "SELLO LARGO",
                    "name_normalized": "SELLO LARGO",
                    "category_path": None,
                    "quantity_available": -2,
                    "image_status": "present",
                    "brand": "NATSUKI",
                    "family": "empaques",
                },
            },
        ]

    def close(self) -> None:
        self.closed = True

    def plan(self) -> tuple[str, int, int]:
        return "muestra_sintetica", len(self.rows), len(self.rows)

    def search(
        self,
        query: str,
        category: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        query = query.upper()
        category = category.upper()
        matches = [
            item
            for item in self.rows
            if query
            in f"{item['data']['internal_reference_normalized']} {item['data']['name_normalized']}"
            and category in str(item["data"].get("category_path") or "").upper()
        ]
        return matches[offset : offset + limit]

    def product(self, source_row_number: int) -> dict[str, Any] | None:
        return next((item for item in self.rows if item["row"] == source_row_number), None)

    def categories(self) -> list[dict[str, Any]]:
        return [
            {"value": "Todos / Empaques", "count": 1},
            {"value": None, "count": 1},
        ]


class CatalogApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.repository = SyntheticCatalogRepository()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(self.repository)),
            base_url="http://testserver",
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_health_and_openapi_are_available(self) -> None:
        response = await self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "api_version": "1.0.0"})
        self.assertIn("/api/v1/products", (await self.client.get("/openapi.json")).json()["paths"])

    async def test_products_support_search_category_and_pagination(self) -> None:
        response = await self.client.get(
            "/api/v1/products",
            params={"q": "empaque", "category": "Todos", "limit": 1, "offset": 0},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["total_catalog"], 2)
        self.assertEqual(payload["items"][0]["reference"], "001-A-00")
        self.assertEqual(payload["items"][0]["id"], "source-row:2")
        self.assertEqual(payload["items"][0]["identity_status"], "provisional_source_row")

    async def test_product_preserves_zero_negative_and_missing_values(self) -> None:
        first = (await self.client.get("/api/v1/products/2")).json()
        second = (await self.client.get("/api/v1/products/3")).json()
        self.assertEqual(first["quantity_available"], 0)
        self.assertEqual(second["quantity_available"], -2)
        self.assertIsNone(second["category"])

    async def test_missing_product_returns_404(self) -> None:
        response = await self.client.get("/api/v1/products/999")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Producto no encontrado")

    async def test_categories_include_missing_value_bucket(self) -> None:
        response = await self.client.get("/api/v1/categories")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][-1], {"value": None, "count": 1})

    async def test_existing_html_catalog_and_print_routes_remain_available(self) -> None:
        self.assertIn("001-A-00", (await self.client.get("/", params={"q": "001"})).text)
        self.assertIn("EMPAQUE SINTÉTICO ÁRBOL", (await self.client.get("/producto/2")).text)
        self.assertNotIn("Volver al catálogo", (await self.client.get("/producto/2/ficha")).text)


if __name__ == "__main__":
    unittest.main()
