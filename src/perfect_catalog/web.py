from __future__ import annotations

import html
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qs, unquote, urlencode, urlparse

import psycopg

from tools.odoo_profiler import read_tabular_source

from .canonical import normalize_name
from .config import DatabaseConfig
from .importer import prepare_rows, validate_headers
from .releases import (
    release_snapshot_sha256,
    validate_release_definition,
    validate_release_item,
    validate_release_items,
)


PAGE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Perfect Trading Catalog</title>
<style>
:root {{ color-scheme: light; --ink:#17242a; --muted:#637279; --line:#dbe4e6; --paper:#f6f8f6; --card:#fff; --accent:#0f766e; --accent-dark:#115e59; --warm:#e9b949; }}
* {{ box-sizing:border-box; }} body {{ margin:0; color:var(--ink); background:var(--paper); font-family: Georgia, 'Times New Roman', serif; }}
.shell {{ max-width:1180px; margin:0 auto; padding:32px 22px 56px; }}
header {{ display:flex; justify-content:space-between; gap:20px; align-items:end; border-bottom:1px solid var(--line); padding-bottom:24px; }}
.eyebrow {{ color:var(--accent); font:700 12px/1.2 Arial,sans-serif; letter-spacing:2px; text-transform:uppercase; }}
h1 {{ font-size:clamp(36px,6vw,70px); line-height:.95; margin:10px 0 0; font-weight:500; }}
.header-note {{ max-width:250px; color:var(--muted); font:14px/1.5 Arial,sans-serif; text-align:right; }}
.search {{ display:grid; grid-template-columns:1fr 260px auto; gap:10px; margin:28px 0 14px; }}
input, button {{ min-height:48px; border:1px solid var(--line); border-radius:4px; padding:0 14px; font:15px Arial,sans-serif; }}
input {{ background:var(--card); color:var(--ink); }} button {{ background:var(--accent); color:#fff; border-color:var(--accent); cursor:pointer; font-weight:700; }} button:hover {{ background:var(--accent-dark); }}
.stats {{ display:flex; flex-wrap:wrap; gap:10px; margin:0 0 22px; font:13px Arial,sans-serif; color:var(--muted); }} .stat {{ background:#e7efed; padding:8px 11px; border-radius:3px; }} .stat strong {{ color:var(--ink); }}
.category-strip {{ display:flex; gap:8px; overflow:auto; padding:3px 0 22px; scrollbar-width:thin; }} .category-strip a {{ flex:none; padding:9px 12px; border:1px solid var(--line); border-radius:999px; color:var(--muted); background:#fff; font:12px Arial,sans-serif; text-decoration:none; }} .category-strip a.active {{ color:#fff; border-color:var(--accent); background:var(--accent); }}
.results {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }} .result {{ min-width:0; background:var(--card); border:1px solid var(--line); display:flex; flex-direction:column; overflow:hidden; }}
.result-visual {{ min-height:150px; display:grid; place-items:center; position:relative; color:var(--accent-dark); background:linear-gradient(145deg,#edf4f2,#faf8ef); text-decoration:none; overflow:hidden; }} .result-visual span {{ width:54px; height:54px; display:grid; place-items:center; border:1px solid currentColor; border-radius:50%; font:700 17px Arial,sans-serif; }} .result-visual img {{ width:100%; height:190px; object-fit:contain; background:#fff; }} .result-visual.present::after {{ content:'imagen asociada'; position:absolute; right:10px; bottom:9px; padding:3px 5px; color:#fff; background:var(--accent); font:700 9px Arial,sans-serif; letter-spacing:.08em; text-transform:uppercase; }} .result-body {{ display:flex; flex:1; flex-direction:column; padding:18px; }}
.ref {{ font:700 15px Arial,sans-serif; color:var(--accent-dark); }} .ref a {{ color:inherit; text-decoration:none; }} .name {{ min-height:2.4em; font-size:21px; line-height:1.2; margin:9px 0; }} .meta {{ color:var(--muted); font:12px/1.5 Arial,sans-serif; }} .result-footer {{ display:flex; justify-content:space-between; gap:12px; align-items:end; margin-top:auto; padding-top:18px; }} .qty {{ text-align:right; font:700 18px Arial,sans-serif; }} .qty small {{ display:block; color:var(--muted); font-size:10px; font-weight:400; }} .brand-chip {{ padding:5px 7px; color:var(--accent-dark); background:#e7efed; font:700 10px Arial,sans-serif; text-transform:uppercase; }}
.empty {{ padding:42px 20px; color:var(--muted); text-align:center; border:1px dashed var(--line); font:15px Arial,sans-serif; }}
.pagination {{ display:flex; justify-content:space-between; align-items:center; gap:12px; padding:28px 0 0; font:13px Arial,sans-serif; }} .pagination a {{ padding:11px 15px; color:#fff; background:var(--accent); text-decoration:none; }} .pagination .disabled {{ visibility:hidden; }}
@media(max-width:900px) {{ .results {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} }} @media(max-width:620px) {{ header {{ display:block; }} .header-note {{ text-align:left; margin-top:16px; }} .search,.results {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body><main class="shell">
<header><div><div class="eyebrow">Perfect Trading / Natsuki</div><h1>Catálogo de empaques</h1></div><div class="header-note">Consulta local de la muestra importada desde Odoo. Datos en revisión, sin cambios empresariales.</div></header>
<form class="search" method="get"><input name="q" value="{query}" placeholder="Referencia o nombre" autofocus><input name="category" value="{category}" placeholder="Categoría contiene"><button type="submit">Buscar</button></form>
<nav class="category-strip" aria-label="Categorías del catálogo">{categories}</nav>
<div class="stats"><span class="stat">Plan <strong>{plan_status}</strong></span><span class="stat">Referencias <strong>{total}</strong></span><span class="stat">Resultados <strong>{shown}</strong></span><span class="stat">Página <strong>{page}</strong></span><span class="stat">Fuente <strong>Odoo</strong></span></div>
<section class="results">{results}</section>
{pagination}
</main></body></html>"""


class CatalogReader(Protocol):
    def close(self) -> None: ...

    def plan(self) -> tuple[str, int, int]: ...

    def search(
        self,
        query: str,
        category: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]: ...

    def product(self, product_id: str) -> dict[str, Any] | None: ...

    def categories(self) -> list[dict[str, Any]]: ...


def _source_row_number(product_id: str) -> int | None:
    value = str(product_id).removeprefix("source-row:")
    try:
        return int(value)
    except ValueError:
        return None


def _provisional_item(source_row_number: int, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"source-row:{source_row_number}",
        "identity_status": "provisional_source_row",
        "row": source_row_number,
        "data": data,
    }


def _identity_label(item: dict[str, Any]) -> str:
    if item.get("identity_status") == "published_uuid":
        return f"UUID publicado {item['id']}"
    return f"Fila Odoo {item.get('row', 'desconocida')}"


class CatalogRepository:
    def __init__(self, config: DatabaseConfig, password: str) -> None:
        self.connection = psycopg.connect(**config.connection_kwargs(password), autocommit=True)

    def close(self) -> None:
        self.connection.close()

    def plan(self) -> tuple[str, int, int]:
        row = self.connection.execute(
            """
            SELECT p.plan_status, count(DISTINCT sr.staging_row_id), count(DISTINCT sr.staging_row_id)
            FROM perfect_catalog.import_plan p
            JOIN perfect_catalog.import_file f ON f.import_file_id = p.import_file_id
            JOIN perfect_catalog.staging_row sr ON sr.import_file_id = f.import_file_id
            WHERE p.import_plan_id = (SELECT import_plan_id FROM perfect_catalog.import_plan ORDER BY generated_at DESC LIMIT 1)
            GROUP BY p.plan_status
            """
        ).fetchone()
        return (str(row[0]), int(row[1]), int(row[2])) if row else ("sin_plan", 0, 0)

    def search(
        self,
        query: str,
        category: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        like_query = f"%{query}%"
        like_category = f"%{category}%"
        rows = self.connection.execute(
            """
            SELECT sr.source_row_number, r.normalized_data
            FROM perfect_catalog.staging_row_result r
            JOIN perfect_catalog.staging_row sr ON sr.staging_row_id = r.staging_row_id
            WHERE r.import_batch_id = (SELECT import_batch_id FROM perfect_catalog.import_plan ORDER BY generated_at DESC LIMIT 1)
              AND r.processing_stage = 'reconciled'
              AND (r.normalized_data->>'internal_reference_normalized' ILIKE %s
                   OR r.normalized_data->>'name_normalized' ILIKE %s)
              AND r.normalized_data->>'category_path' ILIKE %s
            ORDER BY r.normalized_data->>'internal_reference_normalized'
            LIMIT %s OFFSET %s
            """,
            (like_query, like_query, like_category, limit, offset),
        ).fetchall()
        return [_provisional_item(int(source_row), data) for source_row, data in rows]

    def product(self, product_id: str) -> dict[str, Any] | None:
        source_row_number = _source_row_number(product_id)
        if source_row_number is None:
            return None
        row = self.connection.execute(
            """
            SELECT sr.source_row_number, r.normalized_data
            FROM perfect_catalog.staging_row_result AS r
            JOIN perfect_catalog.staging_row AS sr ON sr.staging_row_id = r.staging_row_id
            WHERE r.import_batch_id = (
                SELECT import_batch_id
                FROM perfect_catalog.import_plan
                ORDER BY generated_at DESC
                LIMIT 1
            )
              AND r.processing_stage = 'reconciled'
              AND sr.source_row_number = %s
            ORDER BY r.created_at DESC
            LIMIT 1
            """,
            (source_row_number,),
        ).fetchone()
        return _provisional_item(int(row[0]), row[1]) if row else None

    def categories(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT r.normalized_data->>'category_path' AS category, count(*)
            FROM perfect_catalog.staging_row_result AS r
            WHERE r.import_batch_id = (
                SELECT import_batch_id
                FROM perfect_catalog.import_plan
                ORDER BY generated_at DESC
                LIMIT 1
            )
              AND r.processing_stage = 'reconciled'
            GROUP BY r.normalized_data->>'category_path'
            ORDER BY r.normalized_data->>'category_path' NULLS LAST
            """
        ).fetchall()
        return [
            {"value": str(category) if category is not None else None, "count": int(count)}
            for category, count in rows
        ]


class ReleaseCatalogRepository:
    def __init__(self, config: DatabaseConfig, password: str, brand: str = "NATSUKI") -> None:
        self.connection = psycopg.connect(
            **config.connection_kwargs(password), autocommit=True
        )
        self._owns_connection = True
        try:
            self._initialize(brand)
        except Exception:
            self.connection.close()
            raise

    @classmethod
    def from_connection(
        cls, connection: Any, brand: str = "NATSUKI"
    ) -> "ReleaseCatalogRepository":
        repository = cls.__new__(cls)
        repository.connection = connection
        repository._owns_connection = False
        repository._initialize(brand)
        return repository

    def _initialize(self, brand: str) -> None:
        release = self.connection.execute(
            """
            SELECT r.catalog_release_id, r.brand_id, r.version, r.status,
                   r.snapshot_sha256, r.definition
            FROM perfect_catalog.catalog_release AS r
            JOIN perfect_catalog.brand AS b ON b.brand_id = r.brand_id
            WHERE r.status='published' AND b.normalized_name=%s
            ORDER BY r.published_at DESC, r.created_at DESC, r.catalog_release_id DESC
            LIMIT 1
            """,
            (normalize_name(brand),),
        ).fetchone()
        if release is None:
            raise FileNotFoundError(
                f"No existe un catalog_release publicado para la marca {brand}."
            )
        self.release_id = release[0]
        self.brand_id = release[1]
        self.version = str(release[2])
        self.status = str(release[3])
        self.snapshot_sha256 = str(release[4])
        definition = release[5]
        rows = self.connection.execute(
            """
            SELECT item_order, product_template_id, product_variant_id,
                   snapshot_schema_version, snapshot_data, snapshot_sha256
            FROM perfect_catalog.catalog_release_item
            WHERE catalog_release_id=%s
            ORDER BY item_order
            """,
            (self.release_id,),
        ).fetchall()
        if not rows:
            raise ValueError("El release publicado no contiene productos.")
        validate_release_definition(definition, len(rows))
        items = [
            {
                "item_order": row[0],
                "product_template_id": row[1],
                "product_variant_id": row[2],
                "snapshot_schema_version": row[3],
                "snapshot_data": row[4],
                "snapshot_sha256": row[5],
            }
            for row in rows
        ]
        validate_release_items(items)
        recalculated = release_snapshot_sha256(
            self.brand_id, self.version, definition, items
        )
        if recalculated != self.snapshot_sha256:
            raise ValueError("Los items publicados no coinciden con snapshot_sha256 del release.")
        self.total = len(items)

    def close(self) -> None:
        if self._owns_connection:
            self.connection.close()

    def plan(self) -> tuple[str, int, int]:
        return (f"published:{self.version}", self.total, self.total)

    @staticmethod
    def _item(row: tuple[Any, ...]) -> dict[str, Any]:
        item = {
            "item_order": row[0],
            "product_template_id": row[1],
            "product_variant_id": row[2],
            "snapshot_schema_version": row[3],
            "snapshot_data": row[4],
            "snapshot_sha256": row[5],
        }
        validate_release_item(item)
        target_id = item["product_variant_id"] or item["product_template_id"]
        data = item["snapshot_data"]
        source_row = data.get("source_row_number")
        return {
            "id": str(target_id),
            "identity_status": "published_uuid",
            "row": source_row if isinstance(source_row, int) else None,
            "data": data,
        }

    def search(
        self,
        query: str,
        category: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        like_query = f"%{query}%"
        like_category = f"%{category}%"
        rows = self.connection.execute(
            """
            SELECT item_order, product_template_id, product_variant_id,
                   snapshot_schema_version, snapshot_data, snapshot_sha256
            FROM perfect_catalog.catalog_release_item
            WHERE catalog_release_id=%s
              AND (
                    COALESCE(snapshot_data->>'internal_reference_normalized', '') ILIKE %s
                    OR COALESCE(snapshot_data->>'name_normalized', '') ILIKE %s
              )
              AND COALESCE(snapshot_data->>'category_path', '') ILIKE %s
            ORDER BY item_order
            LIMIT %s OFFSET %s
            """,
            (self.release_id, like_query, like_query, like_category, limit, offset),
        ).fetchall()
        return [self._item(row) for row in rows]

    def product(self, product_id: str) -> dict[str, Any] | None:
        try:
            target_id = uuid.UUID(str(product_id))
        except ValueError:
            return None
        row = self.connection.execute(
            """
            SELECT item_order, product_template_id, product_variant_id,
                   snapshot_schema_version, snapshot_data, snapshot_sha256
            FROM perfect_catalog.catalog_release_item
            WHERE catalog_release_id=%s
              AND COALESCE(product_variant_id, product_template_id)=%s
            LIMIT 1
            """,
            (self.release_id, target_id),
        ).fetchone()
        return self._item(row) if row else None

    def categories(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT NULLIF(btrim(snapshot_data->>'category_path'), '') AS category,
                   count(*)
            FROM perfect_catalog.catalog_release_item
            WHERE catalog_release_id=%s
            GROUP BY NULLIF(btrim(snapshot_data->>'category_path'), '')
            ORDER BY category NULLS LAST
            """,
            (self.release_id,),
        ).fetchall()
        return [
            {"value": str(category) if category is not None else None, "count": int(count)}
            for category, count in rows
        ]


class ExcelCatalogRepository:
    def __init__(self, source_path: str) -> None:
        sheets = read_tabular_source(Path(source_path))
        if len(sheets) != 1 or not sheets[0].rows:
            raise ValueError("El catálogo local requiere exactamente una hoja no vacía.")
        sheet = sheets[0]
        headers = validate_headers(sheet.rows[0])
        self.rows = prepare_rows(sheet.name, headers, sheet.rows[1:], sheet.row_numbers[1:])

    def close(self) -> None:
        return

    def plan(self) -> tuple[str, int, int]:
        return ("muestra_local", len(self.rows), len(self.rows))

    def search(
        self,
        query: str,
        category: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        query_upper = query.upper()
        category_upper = category.upper()
        matches = []
        skipped = 0
        for row in self.rows:
            data = row.normalized
            haystack = f"{data['internal_reference_normalized']} {data['name_normalized']}"
            if query_upper not in haystack or category_upper not in str(data.get("category_path") or "").upper():
                continue
            if skipped < offset:
                skipped += 1
                continue
            matches.append(_provisional_item(row.source_row_number, data))
            if len(matches) >= limit:
                break
        return matches

    def product(self, product_id: str) -> dict[str, Any] | None:
        source_row_number = _source_row_number(product_id)
        if source_row_number is None:
            return None
        for row in self.rows:
            if row.source_row_number == source_row_number:
                return _provisional_item(row.source_row_number, row.normalized)
        return None

    def categories(self) -> list[dict[str, Any]]:
        counts: dict[str | None, int] = {}
        for row in self.rows:
            value = row.normalized.get("category_path")
            category = str(value) if value is not None and str(value).strip() else None
            counts[category] = counts.get(category, 0) + 1
        return [
            {"value": category, "count": counts[category]}
            for category in sorted(counts, key=lambda value: (value is None, value or ""))
        ]


class AutoExcelCatalogRepository:
    def __init__(self, source_dir: Path) -> None:
        self.source_dir = source_dir
        self._repository: ExcelCatalogRepository | None = None
        self._source_signature: tuple[str, int] | None = None
        self._lock = threading.Lock()

    def _latest_source(self) -> Path:
        sources = sorted(
            self.source_dir.glob("*.xlsx"),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )
        if not sources:
            raise FileNotFoundError(f"No hay archivos XLSX en {self.source_dir}")
        return sources[0]

    def _current(self) -> ExcelCatalogRepository:
        source = self._latest_source()
        signature = (str(source.resolve()), source.stat().st_mtime_ns)
        with self._lock:
            if self._repository is None or self._source_signature != signature:
                self._repository = ExcelCatalogRepository(str(source))
                self._source_signature = signature
            return self._repository

    def close(self) -> None:
        return

    def plan(self) -> tuple[str, int, int]:
        return self._current().plan()

    def search(
        self,
        query: str,
        category: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return self._current().search(query, category, limit, offset)

    def product(self, product_id: str) -> dict[str, Any] | None:
        return self._current().product(product_id)

    def categories(self) -> list[dict[str, Any]]:
        return self._current().categories()


def render_results(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<div class="empty">No hay resultados para esta búsqueda.</div>'
    rendered = []
    for item in items:
        data = item["data"]
        raw_reference = str(data.get("internal_reference_original") or "Sin referencia")
        reference = html.escape(raw_reference)
        initials = html.escape(raw_reference[:2])
        image_status = "present" if data.get("image_status") == "present" else "absent"
        product_url = f'/producto/{html.escape(str(item["id"]), quote=True)}'
        visual = (
            f'<img src="/media/{html.escape(str(item["id"]), quote=True)}" alt="{reference}" loading="lazy">'
            if data.get("image_storage_relpath") and data.get("image_sha256") else f'<span>{initials}</span>'
        )
        quantity_value = data.get("quantity_available")
        quantity = 0 if quantity_value is None else quantity_value
        rendered.append(
            '<article class="result">'
            f'<a class="result-visual {image_status}" href="{product_url}">{visual}</a>'
            f'<div class="result-body"><div class="ref"><a href="{product_url}">{reference}</a></div>'
            f'<div class="name">{html.escape(str(data.get("name_original") or ""))}</div>'
            f'<div class="meta">{html.escape(str(data.get("category_path") or "Sin categoría"))}</div>'
            f'<div class="result-footer"><span class="brand-chip">{html.escape(str(data.get("brand") or "Perfect"))}</span>'
            f'<div class="qty"><small>Disponible</small>{html.escape(str(quantity))}</div></div></div>'
            '</article>'
        )
    return "".join(rendered)


def render_category_filters(
    categories: list[dict[str, Any]], selected: str, query: str = ""
) -> str:
    all_query = urlencode({"q": query}) if query else ""
    links = [f'<a class="{"active" if not selected else ""}" href="/?{all_query}">Todas</a>']
    for item in categories[:30]:
        value = item.get("value")
        if value is None or not str(value).strip():
            continue
        value = str(value)
        target = urlencode({"q": query, "category": value})
        active = "active" if value == selected else ""
        links.append(
            f'<a class="{active}" href="/?{target}">{html.escape(value)} · {int(item.get("count") or 0)}</a>'
        )
    return "".join(links)


def render_pagination(
    query: str, category: str, page: int, has_next: bool
) -> str:
    def target(number: int) -> str:
        return "/?" + urlencode({"q": query, "category": category, "page": number})

    previous = (
        f'<a href="{target(page - 1)}">← Anterior</a>'
        if page > 1 else '<span class="disabled">Anterior</span>'
    )
    following = (
        f'<a href="{target(page + 1)}">Siguiente →</a>'
        if has_next else '<span class="disabled">Siguiente</span>'
    )
    return f'<nav class="pagination" aria-label="Páginas del catálogo">{previous}<strong>Página {page}</strong>{following}</nav>'


def render_product(product: dict[str, Any], printable: bool = False) -> str:
    data = product["data"]
    title = html.escape(str(data.get("name_original") or "Producto Natsuki"))
    reference = html.escape(str(data.get("internal_reference_original") or ""))
    category = html.escape(str(data.get("category_path") or "Sin categoría"))
    quantity = html.escape(str(data.get("quantity_available") or 0))
    currency = html.escape(str(data.get("currency") or ""))
    image_status = html.escape(str(data.get("image_status") or "absent"))
    media_url = f'/media/{html.escape(str(product["id"]), quote=True)}'
    image_panel = (
        f'<div class="image has-media"><img src="{media_url}" alt="{reference}"></div>'
        if data.get("image_storage_relpath") and data.get("image_sha256")
        else f'<div class="image">Imagen: {image_status}<br><small>Sin imagen aprobada en este release.</small></div>'
    )
    applications = [html.escape(str(value)) for value in data.get("applications") or []]
    oem_references = [html.escape(str(value)) for value in data.get("oem_references") or []]
    applications_fact = (
        f'<div class="fact stacked"><span class="label">Aplicaciones</span><strong>{"; ".join(applications)}</strong></div>'
        if applications else ""
    )
    oem_fact = (
        f'<div class="fact stacked"><span class="label">Referencias OEM</span><strong>{", ".join(oem_references)}</strong></div>'
        if oem_references else ""
    )
    back = '<a class="back" href="/">Volver al catálogo</a>' if not printable else ''
    print_link = f'<a class="print-link" href="/producto/{html.escape(str(product["id"]), quote=True)}/ficha">Ficha imprimible / PDF</a>' if not printable else ''
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{reference} - Natsuki</title><style>
:root {{ --ink:#17242a; --muted:#637279; --line:#dbe4e6; --accent:#0f766e; --warm:#e9b949; --paper:#f6f8f6; }}
* {{ box-sizing:border-box; }} body {{ margin:0; background:var(--paper); color:var(--ink); font-family:Georgia,'Times New Roman',serif; }}
.sheet {{ max-width:900px; margin:0 auto; padding:34px 22px 60px; }} .back,.print-link {{ font:14px Arial,sans-serif; color:var(--accent); text-decoration:none; }}
.top {{ display:flex; justify-content:space-between; gap:20px; border-bottom:1px solid var(--line); padding-bottom:18px; }}
.eyebrow {{ color:var(--accent); font:700 12px Arial,sans-serif; letter-spacing:2px; text-transform:uppercase; }} h1 {{ font-size:clamp(30px,5vw,58px); line-height:1; margin:12px 0 8px; font-weight:500; }}
.ref {{ color:var(--accent); font:700 22px Arial,sans-serif; }} .actions {{ display:flex; gap:14px; align-items:start; }}
.hero {{ display:grid; grid-template-columns:1fr 1fr; gap:26px; padding:30px 0; }} .image {{ min-height:300px; border:1px dashed var(--line); display:grid; place-items:center; color:var(--muted); font:14px Arial,sans-serif; text-align:center; padding:30px; }} .image.has-media {{ padding:0; border-style:solid; background:#fff; }} .image img {{ width:100%; height:100%; max-height:480px; object-fit:contain; }}
.facts {{ background:#fff; border:1px solid var(--line); padding:22px; }} .fact {{ display:flex; justify-content:space-between; gap:18px; padding:12px 0; border-bottom:1px solid var(--line); font:14px Arial,sans-serif; }} .fact.stacked {{ display:grid; }} .fact:last-child {{ border-bottom:0; }} .label {{ color:var(--muted); }}
.notice {{ border-left:4px solid var(--warm); padding:14px 16px; background:#fff8e8; font:14px/1.5 Arial,sans-serif; }}
@media print {{ body {{ background:#fff; }} .actions,.back {{ display:none; }} .sheet {{ padding:0; }} }} @media(max-width:700px) {{ .hero {{ grid-template-columns:1fr; }} .top {{ display:block; }} .actions {{ margin-top:18px; }} }}
</style></head><body><main class="sheet">{back}<div class="top"><div><div class="eyebrow">Perfect Trading / Natsuki</div><h1>{title}</h1><div class="ref">{reference}</div></div><div class="actions">{print_link}</div></div>
<section class="hero">{image_panel}<div class="facts"><div class="fact"><span class="label">Categoría</span><strong>{category}</strong></div><div class="fact"><span class="label">Disponible</span><strong>{quantity} {currency}</strong></div>{applications_fact}{oem_fact}<div class="fact"><span class="label">Identidad</span><strong>{_identity_label(product)}</strong></div></div></section>
<div class="notice">Ficha basada en la exportación preliminar de Odoo. Los campos no presentes en la muestra, como aplicaciones, OEM, FMSI y especificaciones técnicas, permanecen pendientes de futuras fuentes.</div>
</main></body></html>"""


def make_handler(repository: CatalogReader) -> type[BaseHTTPRequestHandler]:
    class CatalogHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                params = parse_qs(parsed.query)
                query = params.get("q", [""])[0].strip()
                category = params.get("category", [""])[0].strip()
                try:
                    page = int(params.get("page", ["1"])[0])
                except ValueError:
                    page = 1
                page = min(10000, max(1, page))
                status, total, _ = repository.plan()
                page_size = 48
                page_items = repository.search(
                    query, category, page_size + 1, (page - 1) * page_size
                )
                has_next = len(page_items) > page_size
                items = page_items[:page_size]
                categories = repository.categories()
                body = PAGE.format(
                    query=html.escape(query, quote=True),
                    category=html.escape(category, quote=True),
                    plan_status=html.escape(status),
                    total=total,
                    shown=len(items),
                    page=page,
                    categories=render_category_filters(categories, category, query),
                    results=render_results(items),
                    pagination=render_pagination(query, category, page, has_next),
                ).encode("utf-8")
            elif parsed.path.startswith("/producto/"):
                parts = parsed.path.strip("/").split("/")
                try:
                    product = repository.product(unquote(parts[1]))
                except IndexError:
                    product = None
                if product is None:
                    self.send_error(404)
                    return
                body = render_product(product, len(parts) > 2 and parts[2] == "ficha").encode("utf-8")
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    return CatalogHandler


def serve(repository: CatalogReader, host: str = "127.0.0.1", port: int = 8080) -> None:
    server = ThreadingHTTPServer((host, port), make_handler(repository))
    print(f"Catálogo local: http://{host}:{port}")
    print("Solo lectura. Presiona Ctrl+C para detener.")
    try:
        server.serve_forever()
    finally:
        server.server_close()
        repository.close()
