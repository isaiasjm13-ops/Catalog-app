from __future__ import annotations

import html
import uuid
from typing import Any, Protocol
from urllib.parse import urlencode

import psycopg

from .canonical import normalize_name
from .config import DatabaseConfig
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
<title>{catalog_title}</title>
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
<header><div><div class="eyebrow">{eyebrow}</div><h1>{catalog_title}</h1></div><div class="header-note">Catálogo publicado de solo lectura, sin cambios empresariales.</div></header>
<form class="search" method="get"><input name="q" value="{query}" placeholder="Referencia o nombre" autofocus><input name="category" value="{category}" placeholder="Categoría contiene"><button type="submit">Buscar</button></form>
<nav class="category-strip" aria-label="Categorías del catálogo">{categories}</nav>
<div class="stats"><span class="stat">Plan <strong>{plan_status}</strong></span><span class="stat">Referencias <strong>{total}</strong></span><span class="stat">Resultados <strong>{shown}</strong></span><span class="stat">Página <strong>{page}</strong></span><span class="stat">Fuente <strong>Odoo</strong></span></div>
<section class="results">{results}</section>
{pagination}
</main></body></html>"""


class CatalogReader(Protocol):
    brand_name: str

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


def _identity_label(item: dict[str, Any]) -> str:
    return f"UUID publicado {item['id']}"


class ReleaseCatalogRepository:
    def __init__(self, config: DatabaseConfig, password: str, brand: str) -> None:
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
        cls, connection: Any, brand: str
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
                   r.snapshot_sha256, r.definition, b.name, b.code
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
        self.brand_name = str(release[6])
        self.brand_code = str(release[7])
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
        data = dict(item["snapshot_data"])
        for excluded in (
            "quantity_available", "quantity_on_hand", "uom_original", "currency",
            "price", "price_two", "responsible", "product_tags",
        ):
            data.pop(excluded, None)
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
        rendered.append(
            '<article class="result">'
            f'<a class="result-visual {image_status}" href="{product_url}">{visual}</a>'
            f'<div class="result-body"><div class="ref"><a href="{product_url}">{reference}</a></div>'
            f'<div class="name">{html.escape(str(data.get("name_original") or ""))}</div>'
            f'<div class="meta">{html.escape(str(data.get("category_path") or "Sin categoría"))}</div>'
            f'<div class="result-footer"><span class="brand-chip">{html.escape(str(data.get("brand") or ""))}</span></div></div>'
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


def render_product(product: dict[str, Any], printable: bool = False, brand_name: str = "Catálogo") -> str:
    data = product["data"]
    eyebrow = html.escape(brand_name)
    title = html.escape(str(data.get("name_original") or "Producto sin nombre"))
    reference = html.escape(str(data.get("internal_reference_original") or ""))
    category = html.escape(str(data.get("category_path") or "Sin categoría"))
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
<title>{reference} - {eyebrow}</title><style>
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
</style></head><body><main class="sheet">{back}<div class="top"><div><div class="eyebrow">{eyebrow}</div><h1>{title}</h1><div class="ref">{reference}</div></div><div class="actions">{print_link}</div></div>
<section class="hero">{image_panel}<div class="facts"><div class="fact"><span class="label">Categoría</span><strong>{category}</strong></div>{applications_fact}{oem_fact}<div class="fact"><span class="label">Identidad</span><strong>{_identity_label(product)}</strong></div></div></section>
<div class="notice">Ficha del release publicado. Los campos ausentes, como aplicaciones, OEM, FMSI y especificaciones técnicas, no están disponibles en este catálogo.</div>
</main></body></html>"""


