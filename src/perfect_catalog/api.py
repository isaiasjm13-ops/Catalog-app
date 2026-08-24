from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .web import (
    PAGE,
    AutoExcelCatalogRepository,
    CatalogReader,
    ExcelCatalogRepository,
    render_product,
    render_results,
)


API_VERSION = "1.0.0"


class StrictResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(StrictResponse):
    status: str
    api_version: str


class ProductResource(StrictResponse):
    id: str
    identity_status: str
    source_row_number: int
    reference: str
    name: str
    category: str | None
    quantity_available: int | float | None
    image_status: str
    brand: str | None
    family: str | None


class ProductListResponse(StrictResponse):
    plan_status: str
    total_catalog: int
    count: int
    limit: int
    offset: int
    items: list[ProductResource]


class CategoryResource(StrictResponse):
    value: str | None
    count: int = Field(ge=0)


class CategoryListResponse(StrictResponse):
    count: int
    items: list[CategoryResource]


def _product_resource(item: dict[str, Any]) -> ProductResource:
    data = item["data"]
    row_number = int(item["row"])
    category = data.get("category_path")
    quantity = data.get("quantity_available")
    return ProductResource(
        id=f"source-row:{row_number}",
        identity_status="provisional_source_row",
        source_row_number=row_number,
        reference=str(data.get("internal_reference_original") or ""),
        name=str(data.get("name_original") or ""),
        category=str(category) if category is not None and str(category).strip() else None,
        quantity_available=quantity if isinstance(quantity, (int, float)) and not isinstance(quantity, bool) else None,
        image_status=str(data.get("image_status") or "absent"),
        brand=str(data["brand"]) if data.get("brand") is not None else None,
        family=str(data["family"]) if data.get("family") is not None else None,
    )


def create_app(repository: CatalogReader) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        repository.close()

    app = FastAPI(
        title="Perfect Trading Catalog API",
        version=API_VERSION,
        description=(
            "API de consulta del piloto Natsuki. Los IDs source-row son provisionales "
            "hasta publicar productos con UUID estables."
        ),
        lifespan=lifespan,
    )

    @app.exception_handler(FileNotFoundError)
    async def source_not_found_handler(_, exc: FileNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc), "code": "catalog_source_unavailable"})

    @app.exception_handler(ValueError)
    async def invalid_source_handler(_, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc), "code": "catalog_source_invalid"})

    @app.get("/api/v1/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok", api_version=API_VERSION)

    @app.get("/api/v1/products", response_model=ProductListResponse, tags=["catalog"])
    def products(
        q: str = Query(default="", max_length=200),
        category: str = Query(default="", max_length=300),
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
    ) -> ProductListResponse:
        plan_status, total, _ = repository.plan()
        items = repository.search(q.strip(), category.strip(), limit, offset)
        resources = [_product_resource(item) for item in items]
        return ProductListResponse(
            plan_status=plan_status,
            total_catalog=total,
            count=len(resources),
            limit=limit,
            offset=offset,
            items=resources,
        )

    @app.get("/api/v1/products/{source_row_number}", response_model=ProductResource, tags=["catalog"])
    def product(source_row_number: int) -> ProductResource:
        item = repository.product(source_row_number)
        if item is None:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        return _product_resource(item)

    @app.get("/api/v1/categories", response_model=CategoryListResponse, tags=["catalog"])
    def categories() -> CategoryListResponse:
        items = [CategoryResource(**item) for item in repository.categories()]
        return CategoryListResponse(count=len(items), items=items)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def catalog_page(q: str = "", category: str = "") -> str:
        query = q.strip()
        selected_category = category.strip()
        plan_status, total, _ = repository.plan()
        items = repository.search(query, selected_category)
        import html

        return PAGE.format(
            query=html.escape(query, quote=True),
            category=html.escape(selected_category, quote=True),
            plan_status=html.escape(plan_status),
            total=total,
            shown=len(items),
            results=render_results(items),
        )

    @app.get("/producto/{source_row_number}", response_class=HTMLResponse, include_in_schema=False)
    def product_page(source_row_number: int) -> str:
        item = repository.product(source_row_number)
        if item is None:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        return render_product(item)

    @app.get("/producto/{source_row_number}/ficha", response_class=HTMLResponse, include_in_schema=False)
    def printable_product_page(source_row_number: int) -> str:
        item = repository.product(source_row_number)
        if item is None:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        return render_product(item, printable=True)

    return app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inicia el catálogo FastAPI de solo lectura")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--source", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repository: CatalogReader = (
        ExcelCatalogRepository(str(args.source))
        if args.source is not None
        else AutoExcelCatalogRepository(Path("data/imports"))
    )
    uvicorn.run(create_app(repository), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
