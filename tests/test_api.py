from __future__ import annotations

import unittest
import uuid
import hashlib
import tempfile
import copy
from pathlib import Path
from typing import Any

import httpx

from perfect_catalog.api import API_VERSION, create_app


class SyntheticCatalogRepository:
    def __init__(self) -> None:
        self.closed = False
        self.rows = [
            {
                "id": "source-row:2",
                "identity_status": "provisional_source_row",
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
                "id": "source-row:3",
                "identity_status": "provisional_source_row",
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

    def product(self, product_id: str) -> dict[str, Any] | None:
        source_row_number = int(str(product_id).removeprefix("source-row:"))
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
        self.assertEqual(response.json(), {"status": "ok", "api_version": API_VERSION})
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

    async def test_public_image_requires_release_evidence_path_confinement_and_sha(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            content = b"approved-public-image"
            digest = hashlib.sha256(content).hexdigest()
            target = root / "objects" / digest[:2] / f"{digest}.jpg"
            target.parent.mkdir(parents=True)
            target.write_bytes(content)
            self.repository.rows[0]["data"].update({
                "image_status": "present",
                "image_storage_relpath": f"objects/{digest[:2]}/{digest}.jpg",
                "image_sha256": digest,
                "image_media_type": "image/jpeg",
                "applications": ["Toyota <Corolla>"],
                "oem_references": ["OEM&123"],
            })
            client = httpx.AsyncClient(
                transport=httpx.ASGITransport(app=create_app(self.repository, image_root=root)),
                base_url="http://testserver",
            )
            try:
                page = await client.get("/")
                self.assertIn('src="/media/source-row:2"', page.text)
                detail = await client.get("/producto/2")
                self.assertIn('class="image has-media"', detail.text)
                self.assertIn("Toyota &lt;Corolla&gt;", detail.text)
                self.assertIn("OEM&amp;123", detail.text)
                image = await client.get("/media/source-row:2")
                self.assertEqual(image.status_code, 200)
                self.assertEqual(image.content, content)
                self.assertEqual(image.headers["cache-control"], "no-store")
                target.write_bytes(b"tampered")
                self.assertEqual((await client.get("/media/source-row:2")).status_code, 404)
                self.repository.rows[0]["data"]["image_storage_relpath"] = "../outside.jpg"
                self.assertEqual((await client.get("/media/source-row:2")).status_code, 404)
            finally:
                await client.aclose()

    async def test_existing_html_catalog_and_print_routes_remain_available(self) -> None:
        catalog = (await self.client.get(
            "/", params={"q": "001", "category": "Todos / Empaques"}
        )).text
        self.assertIn("001-A-00", catalog)
        self.assertIn('class="result-visual absent"', catalog)
        self.assertIn("category-strip", catalog)
        self.assertIn("Todos+%2F+Empaques", catalog)
        self.assertIn('class="active"', catalog)
        self.assertIn("EMPAQUE SINTÉTICO ÁRBOL", (await self.client.get("/producto/2")).text)
        self.assertNotIn("Volver al catálogo", (await self.client.get("/producto/2/ficha")).text)

    async def test_public_catalog_paginates_and_preserves_filters(self) -> None:
        repository = SyntheticCatalogRepository()
        prototype = repository.rows[0]
        repository.rows = []
        for index in range(55):
            item = copy.deepcopy(prototype)
            item["id"] = f"source-row:{index + 2}"
            item["row"] = index + 2
            item["data"]["internal_reference_original"] = f"REF-{index:03d}"
            item["data"]["internal_reference_normalized"] = f"REF-{index:03d}"
            repository.rows.append(item)
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(repository)),
            base_url="http://testserver",
        )
        try:
            first = await client.get("/", params={"q": "REF", "category": "Todos", "page": 1})
            self.assertEqual(first.text.count('<article class="result">'), 48)
            self.assertIn("page=2", first.text)
            self.assertIn("category=Todos", first.text)
            second = await client.get("/", params={"q": "REF", "category": "Todos", "page": 2})
            self.assertEqual(second.text.count('<article class="result">'), 7)
            self.assertIn("page=1", second.text)
            self.assertEqual((await client.get("/", params={"page": 0})).status_code, 422)
        finally:
            await client.aclose()

    async def test_published_uuid_is_exposed_without_source_row_identity(self) -> None:
        product_id = uuid.uuid4()

        class PublishedRepository(SyntheticCatalogRepository):
            def __init__(self) -> None:
                super().__init__()
                self.rows = [
                    {
                        "id": str(product_id),
                        "identity_status": "published_uuid",
                        "row": None,
                        "data": self.rows[0]["data"],
                    }
                ]

            def product(self, requested_id: str) -> dict[str, Any] | None:
                return self.rows[0] if requested_id == str(product_id) else None

        repository = PublishedRepository()
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(repository)),
            base_url="http://testserver",
        )
        try:
            resource = (await client.get(f"/api/v1/products/{product_id}")).json()
            self.assertEqual(resource["id"], str(product_id))
            self.assertEqual(resource["identity_status"], "published_uuid")
            self.assertIsNone(resource["source_row_number"])
            self.assertIn(str(product_id), (await client.get("/")).text)
        finally:
            await client.aclose()


if __name__ == "__main__":
    unittest.main()
