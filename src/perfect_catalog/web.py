from __future__ import annotations

import html
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qs, urlparse

import psycopg

from tools.odoo_profiler import read_tabular_source

from .config import DatabaseConfig
from .importer import prepare_rows, validate_headers


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
.search {{ display:grid; grid-template-columns:1fr 220px auto; gap:10px; margin:28px 0 18px; }}
input, button {{ min-height:48px; border:1px solid var(--line); border-radius:4px; padding:0 14px; font:15px Arial,sans-serif; }}
input {{ background:var(--card); color:var(--ink); }} button {{ background:var(--accent); color:#fff; border-color:var(--accent); cursor:pointer; font-weight:700; }} button:hover {{ background:var(--accent-dark); }}
.stats {{ display:flex; flex-wrap:wrap; gap:10px; margin:0 0 22px; font:13px Arial,sans-serif; color:var(--muted); }} .stat {{ background:#e7efed; padding:8px 11px; border-radius:3px; }} .stat strong {{ color:var(--ink); }}
.results {{ display:grid; gap:10px; }} .result {{ background:var(--card); border:1px solid var(--line); border-left:4px solid var(--warm); padding:17px 18px; display:grid; grid-template-columns:minmax(160px, .8fr) 1fr auto; gap:18px; align-items:start; }}
.ref {{ font:700 19px Arial,sans-serif; color:var(--accent-dark); }} .name {{ font-size:20px; margin-bottom:7px; }} .meta {{ color:var(--muted); font:13px/1.5 Arial,sans-serif; }} .qty {{ text-align:right; font:700 18px Arial,sans-serif; }} .qty small {{ display:block; color:var(--muted); font-size:11px; font-weight:400; }}
.empty {{ padding:42px 20px; color:var(--muted); text-align:center; border:1px dashed var(--line); font:15px Arial,sans-serif; }}
@media(max-width:720px) {{ header {{ display:block; }} .header-note {{ text-align:left; margin-top:16px; }} .search {{ grid-template-columns:1fr; }} .result {{ grid-template-columns:1fr; gap:9px; }} .qty {{ text-align:left; }} }}
</style>
</head>
<body><main class="shell">
<header><div><div class="eyebrow">Perfect Trading / Natsuki</div><h1>Catálogo de empaques</h1></div><div class="header-note">Consulta local de la muestra importada desde Odoo. Datos en revisión, sin cambios empresariales.</div></header>
<form class="search" method="get"><input name="q" value="{query}" placeholder="Referencia o nombre" autofocus><input name="category" value="{category}" placeholder="Categoría contiene"><button type="submit">Buscar</button></form>
<div class="stats"><span class="stat">Plan <strong>{plan_status}</strong></span><span class="stat">Referencias <strong>{total}</strong></span><span class="stat">Resultados <strong>{shown}</strong></span><span class="stat">Fuente <strong>Odoo</strong></span></div>
<section class="results">{results}</section>
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

    def product(self, source_row_number: int) -> dict[str, Any] | None: ...

    def categories(self) -> list[dict[str, Any]]: ...


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
        return [{"row": int(source_row), "data": data} for source_row, data in rows]

    def product(self, source_row_number: int) -> dict[str, Any] | None:
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
        return {"row": int(row[0]), "data": row[1]} if row else None

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
            matches.append({"row": row.source_row_number, "data": data})
            if len(matches) >= limit:
                break
        return matches

    def product(self, source_row_number: int) -> dict[str, Any] | None:
        for row in self.rows:
            if row.source_row_number == source_row_number:
                return {"row": row.source_row_number, "data": row.normalized}
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

    def product(self, source_row_number: int) -> dict[str, Any] | None:
        return self._current().product(source_row_number)

    def categories(self) -> list[dict[str, Any]]:
        return self._current().categories()


def render_results(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<div class="empty">No hay resultados para esta búsqueda.</div>'
    rendered = []
    for item in items:
        data = item["data"]
        rendered.append(
            '<article class="result">'
            f'<div><div class="ref"><a href="/producto/{item["row"]}">{html.escape(str(data.get("internal_reference_original") or ""))}</a></div>'
            f'<div class="meta">Fila Odoo {item["row"]}</div></div>'
            f'<div><div class="name">{html.escape(str(data.get("name_original") or ""))}</div>'
            f'<div class="meta">{html.escape(str(data.get("category_path") or "Sin categoría"))}</div></div>'
            f'<div class="qty"><small>Disponible</small>{html.escape(str(data.get("quantity_available") or 0))}</div>'
            '</article>'
        )
    return "".join(rendered)


def render_product(product: dict[str, Any], printable: bool = False) -> str:
    data = product["data"]
    title = html.escape(str(data.get("name_original") or "Producto Natsuki"))
    reference = html.escape(str(data.get("internal_reference_original") or ""))
    category = html.escape(str(data.get("category_path") or "Sin categoría"))
    quantity = html.escape(str(data.get("quantity_available") or 0))
    currency = html.escape(str(data.get("currency") or ""))
    image_status = html.escape(str(data.get("image_status") or "absent"))
    back = '<a class="back" href="/">Volver al catálogo</a>' if not printable else ''
    print_link = f'<a class="print-link" href="/producto/{product["row"]}/ficha">Ficha imprimible / PDF</a>' if not printable else ''
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{reference} - Natsuki</title><style>
:root {{ --ink:#17242a; --muted:#637279; --line:#dbe4e6; --accent:#0f766e; --warm:#e9b949; --paper:#f6f8f6; }}
* {{ box-sizing:border-box; }} body {{ margin:0; background:var(--paper); color:var(--ink); font-family:Georgia,'Times New Roman',serif; }}
.sheet {{ max-width:900px; margin:0 auto; padding:34px 22px 60px; }} .back,.print-link {{ font:14px Arial,sans-serif; color:var(--accent); text-decoration:none; }}
.top {{ display:flex; justify-content:space-between; gap:20px; border-bottom:1px solid var(--line); padding-bottom:18px; }}
.eyebrow {{ color:var(--accent); font:700 12px Arial,sans-serif; letter-spacing:2px; text-transform:uppercase; }} h1 {{ font-size:clamp(30px,5vw,58px); line-height:1; margin:12px 0 8px; font-weight:500; }}
.ref {{ color:var(--accent); font:700 22px Arial,sans-serif; }} .actions {{ display:flex; gap:14px; align-items:start; }}
.hero {{ display:grid; grid-template-columns:1fr 1fr; gap:26px; padding:30px 0; }} .image {{ min-height:300px; border:1px dashed var(--line); display:grid; place-items:center; color:var(--muted); font:14px Arial,sans-serif; text-align:center; padding:30px; }}
.facts {{ background:#fff; border:1px solid var(--line); padding:22px; }} .fact {{ display:flex; justify-content:space-between; gap:18px; padding:12px 0; border-bottom:1px solid var(--line); font:14px Arial,sans-serif; }} .fact:last-child {{ border-bottom:0; }} .label {{ color:var(--muted); }}
.notice {{ border-left:4px solid var(--warm); padding:14px 16px; background:#fff8e8; font:14px/1.5 Arial,sans-serif; }}
@media print {{ body {{ background:#fff; }} .actions,.back {{ display:none; }} .sheet {{ padding:0; }} }} @media(max-width:700px) {{ .hero {{ grid-template-columns:1fr; }} .top {{ display:block; }} .actions {{ margin-top:18px; }} }}
</style></head><body><main class="sheet">{back}<div class="top"><div><div class="eyebrow">Perfect Trading / Natsuki</div><h1>{title}</h1><div class="ref">{reference}</div></div><div class="actions">{print_link}</div></div>
<section class="hero"><div class="image">Imagen: {image_status}<br><small>La muestra no incluye una ruta de archivo utilizable.</small></div><div class="facts"><div class="fact"><span class="label">Categoría</span><strong>{category}</strong></div><div class="fact"><span class="label">Disponible</span><strong>{quantity} {currency}</strong></div><div class="fact"><span class="label">Fila de origen</span><strong>{product["row"]}</strong></div></div></section>
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
                status, total, _ = repository.plan()
                items = repository.search(query, category) if query or category else repository.search("", "")
                body = PAGE.format(
                    query=html.escape(query, quote=True),
                    category=html.escape(category, quote=True),
                    plan_status=html.escape(status),
                    total=total,
                    shown=len(items),
                    results=render_results(items),
                ).encode("utf-8")
            elif parsed.path.startswith("/producto/"):
                parts = parsed.path.strip("/").split("/")
                try:
                    product = repository.product(int(parts[1]))
                except (IndexError, ValueError):
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
