from __future__ import annotations

import argparse
import hashlib
import re
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .web import (
    PAGE,
    AutoExcelCatalogRepository,
    CatalogReader,
    ExcelCatalogRepository,
    ReleaseCatalogRepository,
    render_product,
    render_category_filters,
    render_pagination,
    render_results,
)
from .config import DatabaseConfig, prompt_password


API_VERSION = "1.2.0"


class StrictResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(StrictResponse):
    status: str
    api_version: str


class ProductResource(StrictResponse):
    id: str
    identity_status: str
    source_row_number: int | None
    reference: str
    name: str
    category: str | None
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
    row = item.get("row")
    row_number = int(row) if isinstance(row, int) else None
    category = data.get("category_path")
    return ProductResource(
        id=str(item.get("id") or f"source-row:{row_number}"),
        identity_status=str(item.get("identity_status") or "provisional_source_row"),
        source_row_number=row_number,
        reference=str(data.get("internal_reference_original") or ""),
        name=str(data.get("name_original") or ""),
        category=str(category) if category is not None and str(category).strip() else None,
        image_status=str(data.get("image_status") or "absent"),
        brand=str(data["brand"]) if data.get("brand") is not None else None,
        family=str(data["family"]) if data.get("family") is not None else None,
    )


def create_app(repository: CatalogReader, *, image_root: Path = Path("data/images")) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        repository.close()

    app = FastAPI(
        title="Perfect Trading Catalog API",
        version=API_VERSION,
        description=(
            "API de consulta del catálogo Natsuki. Los releases publicados usan UUID estables; "
            "source-row solo aparece en el modo piloto XLSX explícito."
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

    @app.get("/api/v1/products/{product_id}", response_model=ProductResource, tags=["catalog"])
    def product(product_id: str) -> ProductResource:
        item = repository.product(product_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        return _product_resource(item)

    @app.get("/api/v1/categories", response_model=CategoryListResponse, tags=["catalog"])
    def categories() -> CategoryListResponse:
        items = [CategoryResource(**item) for item in repository.categories()]
        return CategoryListResponse(count=len(items), items=items)

    @app.get("/media/{product_id}", include_in_schema=False)
    def product_image(product_id: str) -> FileResponse:
        item = repository.product(product_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Imagen no encontrada")
        data = item["data"]
        relative = data.get("image_storage_relpath")
        digest = str(data.get("image_sha256") or "")
        if not relative or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise HTTPException(status_code=404, detail="Imagen no encontrada")
        root = image_root.resolve()
        target = (root / str(relative)).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise HTTPException(status_code=404, detail="Imagen no encontrada")
        calculated = hashlib.sha256()
        with target.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                calculated.update(chunk)
        if calculated.hexdigest() != digest:
            raise HTTPException(status_code=404, detail="Imagen no encontrada")
        return FileResponse(
            target, media_type=str(data.get("image_media_type") or "application/octet-stream"),
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def catalog_page(
        q: str = "", category: str = "",
        page: int = Query(default=1, ge=1, le=10000),
    ) -> str:
        query = q.strip()
        selected_category = category.strip()
        plan_status, total, _ = repository.plan()
        page_size = 48
        page_items = repository.search(
            query, selected_category, page_size + 1, (page - 1) * page_size
        )
        has_next = len(page_items) > page_size
        items = page_items[:page_size]
        category_items = repository.categories()
        import html

        return PAGE.format(
            query=html.escape(query, quote=True),
            category=html.escape(selected_category, quote=True),
            plan_status=html.escape(plan_status),
            total=total,
            shown=len(items),
            page=page,
            categories=render_category_filters(category_items, selected_category, query),
            results=render_results(items),
            pagination=render_pagination(query, selected_category, page, has_next),
        )

    @app.get("/producto/{product_id}", response_class=HTMLResponse, include_in_schema=False)
    def product_page(product_id: str) -> str:
        item = repository.product(product_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        return render_product(item)

    @app.get("/producto/{product_id}/ficha", response_class=HTMLResponse, include_in_schema=False)
    def printable_product_page(product_id: str) -> str:
        item = repository.product(product_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        return render_product(item, printable=True)

    return app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inicia el catálogo FastAPI de solo lectura")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--source", type=Path, default=None)
    source.add_argument("--source-dir", type=Path, default=None)
    parser.add_argument("--brand", default="NATSUKI")
    parser.add_argument("--image-root", type=Path, default=Path("data/images"))
    parser.add_argument("--database", default=None)
    parser.add_argument("--user", default=None)
    parser.add_argument("--db-host", dest="host_db", default=None)
    parser.add_argument("--db-port", dest="port_db", type=int, default=None)
    parser.add_argument("--prompt-password", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.source is not None:
            repository: CatalogReader = ExcelCatalogRepository(str(args.source))
        elif args.source_dir is not None:
            repository = AutoExcelCatalogRepository(args.source_dir)
        else:
            database_args = argparse.Namespace(
                host=args.host_db,
                port=args.port_db,
                database=args.database,
                user=args.user,
            )
            config = DatabaseConfig.from_args(database_args)
            repository = ReleaseCatalogRepository(
                config, prompt_password(args.prompt_password), brand=args.brand
            )
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    uvicorn.run(create_app(repository, image_root=args.image_root), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
