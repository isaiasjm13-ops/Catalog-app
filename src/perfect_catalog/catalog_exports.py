from __future__ import annotations

import io
import uuid
from collections import defaultdict
from html import escape
from pathlib import Path
from typing import Any, Iterable

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .releases import release_snapshot_sha256, validate_release_definition, validate_release_items


def export_rows_from_release(release: dict[str, Any], items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Adapta exclusivamente un release completo cuya integridad criptográfica fue revalidada."""
    materialized = sorted(list(items), key=lambda item: item["item_order"])
    validate_release_definition(release["definition"], len(materialized))
    validate_release_items(materialized)
    calculated = release_snapshot_sha256(uuid.UUID(str(release["brand_id"])), str(release["version"]), release["definition"], materialized)
    if calculated != release["snapshot_sha256"]:
        raise ValueError("Los items no coinciden con snapshot_sha256 del release.")
    return [dict(item["snapshot_data"]) for item in materialized]


def _groups(
    rows: list[dict[str, Any]], key: str, secondary_key: str | None = None
) -> list[tuple[str, list[dict[str, Any]]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        primary = str(row.get(key) or "Sin categoría")
        secondary = str(row.get(secondary_key) or "Sin subgrupo") if secondary_key else ""
        grouped[f"{primary} · {secondary}" if secondary else primary].append(row)
    return list(grouped.items())


def _detail(row: dict[str, Any]) -> str:
    parts = [escape(str(row.get("name_original") or "")), f"Ref. {escape(str(row.get('internal_reference_original') or ''))}"]
    if row.get("oem_references"):
        parts.append("OEM: " + escape(", ".join(map(str, row["oem_references"]))))
    if row.get("applications"):
        parts.append("Aplicaciones: " + escape("; ".join(str(value) for value in row["applications"])))
    return "<br/>".join(parts)


def _safe_bundle_image(row: dict[str, Any], bundle_dir: Path | None) -> Path | None:
    if bundle_dir is None or not row.get("image_path"):
        return None
    root = bundle_dir.resolve()
    candidate = (root / str(row["image_path"])).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        return None
    return candidate


def _pdf_cell(row: dict[str, Any], styles: Any, bundle_dir: Path | None) -> list[Any]:
    contents: list[Any] = []
    image_path = _safe_bundle_image(row, bundle_dir)
    if image_path:
        try:
            width, height = ImageReader(str(image_path)).getSize()
            scale = min(4.2 * cm / width, 2.8 * cm / height)
            contents.extend([Image(str(image_path), width=width * scale, height=height * scale), Spacer(1, .12 * cm)])
        except Exception:
            pass
    contents.append(Paragraph(_detail(row), styles["BodyText"]))
    return contents


def generate_catalog_pdf(
    rows: list[dict[str, Any]], config: dict[str, Any] | None = None,
    *, bundle_dir: Path | None = None,
) -> bytes:
    config = config or {}
    columns = max(1, min(3, int(config.get("columns_per_row", 2))))
    title = str(config.get("title") or "Catálogo de productos")
    styles = getSampleStyleSheet()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title=title, leftMargin=1.2*cm, rightMargin=1.2*cm)
    story: list[Any] = [Spacer(1, 6*cm), Paragraph(escape(title), styles["Title"]), Paragraph(escape(str(config.get("subtitle") or "")), styles["Heading2"]), PageBreak()]
    for section, section_rows in _groups(
        rows, str(config.get("group_by") or "category_path"),
        str(config["group_by_secondary"]) if config.get("group_by_secondary") else None,
    ):
        story.extend([Paragraph(escape(section), styles["Heading1"]), Spacer(1, .25*cm)])
        cells = [_pdf_cell(row, styles, bundle_dir) for row in section_rows]
        grid = [cells[index:index+columns] for index in range(0, len(cells), columns)]
        if grid and len(grid[-1]) < columns:
            grid[-1].extend([""] * (columns-len(grid[-1])))
        table = Table(grid, colWidths=[(A4[0]-2.4*cm)/columns]*columns, repeatRows=0)
        table.setStyle(TableStyle([("BOX", (0,0), (-1,-1), .5, colors.HexColor(config.get("primary_color", "#1B3A6B"))), ("INNERGRID", (0,0), (-1,-1), .25, colors.lightgrey), ("VALIGN", (0,0), (-1,-1), "TOP"), ("PADDING", (0,0), (-1,-1), 8)]))
        story.extend([table, Spacer(1, .4*cm)])
    doc.build(story)
    return buffer.getvalue()


def generate_catalog_pptx(
    rows: list[dict[str, Any]], config: dict[str, Any] | None = None,
    *, bundle_dir: Path | None = None,
) -> bytes:
    config = config or {}
    columns = max(1, min(3, int(config.get("columns_per_row", 2))))
    title = str(config.get("title") or "Catálogo de productos")
    prs = Presentation()
    cover = prs.slides.add_slide(prs.slide_layouts[0])
    cover.shapes.title.text = title
    cover.placeholders[1].text = str(config.get("subtitle") or "")
    per_slide = columns * 3
    for section, section_rows in _groups(
        rows, str(config.get("group_by") or "category_path"),
        str(config["group_by_secondary"]) if config.get("group_by_secondary") else None,
    ):
        for start in range(0, len(section_rows), per_slide):
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            heading = slide.shapes.add_textbox(Inches(.4), Inches(.2), Inches(12.5), Inches(.5))
            heading.text_frame.paragraphs[0].text = section
            heading.text_frame.paragraphs[0].font.size = Pt(22)
            heading.text_frame.paragraphs[0].font.bold = True
            for index, row in enumerate(section_rows[start:start+per_slide]):
                col, line = index % columns, index // columns
                width = 12.4 / columns
                box = slide.shapes.add_textbox(Inches(.4+col*width), Inches(.9+line*2.05), Inches(width-.15), Inches(1.85))
                box.fill.solid(); box.fill.fore_color.rgb = RGBColor(245, 247, 250)
                box.line.color.rgb = RGBColor(27, 58, 107)
                frame = box.text_frame; frame.clear()
                image_path = _safe_bundle_image(row, bundle_dir)
                if image_path:
                    try:
                        slide.shapes.add_picture(
                            str(image_path), Inches(.55 + col * width), Inches(1.05 + line * 2.05),
                            height=Inches(.8),
                        )
                        frame.margin_left = Inches(1.15)
                    except Exception:
                        pass
                p = frame.paragraphs[0]; p.text = str(row.get("internal_reference_original") or ""); p.font.bold = True; p.font.size = Pt(12)
                p = frame.add_paragraph(); p.text = str(row.get("name_original") or ""); p.font.size = Pt(11)
                if row.get("applications"):
                    p = frame.add_paragraph(); p.text = "Aplicaciones: " + "; ".join(map(str, row["applications"])); p.font.size = Pt(8)
    output = io.BytesIO(); prs.save(output)
    return output.getvalue()


def generate_catalog_html(
    rows: list[dict[str, Any]], config: dict[str, Any] | None = None,
    *, release: dict[str, Any] | None = None,
) -> bytes:
    """Genera una edición digital portable; no consulta estado mutable ni ejecuta JavaScript."""
    config = config or {}
    release = release or {}
    columns = max(1, min(3, int(config.get("columns_per_row", 2))))
    title = escape(str(config.get("title") or "Catálogo de productos"))
    subtitle = escape(str(config.get("subtitle") or ""))
    sections: list[str] = []
    for section, section_rows in _groups(
        rows, str(config.get("group_by") or "category_path"),
        str(config["group_by_secondary"]) if config.get("group_by_secondary") else None,
    ):
        cards: list[str] = []
        for row in section_rows:
            image = ""
            if row.get("image_path"):
                image = (
                    f'<div class="photo"><img src="{escape(str(row["image_path"]), quote=True)}" '
                    f'alt="{escape(str(row.get("internal_reference_original") or row.get("name_original") or "Producto"), quote=True)}"></div>'
                )
            applications = escape("; ".join(map(str, row.get("applications") or [])))
            cards.append(
                '<article class="product">' + image
                + f'<code>{escape(str(row.get("internal_reference_original") or "Sin referencia"))}</code>'
                + f'<h3>{escape(str(row.get("name_original") or "Sin nombre"))}</h3>'
                + (f'<p>{applications}</p>' if applications else "") + "</article>"
            )
        sections.append(
            f'<section><header><h2>{escape(section)}</h2><span>{len(section_rows)} productos</span></header>'
            f'<div class="products">{"".join(cards)}</div></section>'
        )
    checksum = escape(str(release.get("snapshot_sha256") or ""))
    version = escape(str(release.get("version") or ""))
    html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="generator" content="Perfect Catalog"><meta name="release-sha256" content="{checksum}">
<title>{title}</title><style>
:root{{--ink:#17231f;--forest:#086650;--paper:#f4f1e8;--line:#d9d5c9}}*{{box-sizing:border-box}}body{{margin:0;color:var(--ink);background:var(--paper);font:15px/1.5 Arial,sans-serif}}main{{max-width:1280px;margin:auto;padding:clamp(24px,5vw,72px)}}.hero{{min-height:45vh;display:grid;align-content:end;padding:8vw 0 4vw;border-bottom:4px solid var(--ink)}}.hero small{{color:var(--forest);font-weight:800;letter-spacing:.16em;text-transform:uppercase}}h1{{max-width:900px;margin:.2em 0;font:500 clamp(44px,8vw,104px)/.9 Georgia,serif}}.hero p{{max-width:700px;font-size:18px}}section{{padding:45px 0}}section>header{{display:flex;justify-content:space-between;gap:20px;align-items:end;border-bottom:1px solid var(--line)}}h2{{font:500 clamp(27px,4vw,48px) Georgia,serif}}section>header span{{padding-bottom:1.2em;color:#65716b}}.products{{display:grid;grid-template-columns:repeat({columns},minmax(0,1fr));gap:18px;padding-top:22px}}.product{{min-width:0;padding:18px;background:#fff;border:1px solid var(--line)}}.photo{{height:190px;margin:-18px -18px 18px;background:#f8f8f5;display:grid;place-items:center;overflow:hidden}}.photo img{{width:100%;height:100%;object-fit:contain}}code{{color:var(--forest);font-weight:800}}h3{{margin:.5em 0;font:500 22px/1.15 Georgia,serif}}.proof{{padding:24px 0;border-top:1px solid var(--line);overflow-wrap:anywhere;color:#65716b;font-size:12px}}@media(max-width:760px){{.products{{grid-template-columns:1fr}}.hero{{min-height:35vh}}}}
</style></head><body><main><header class="hero"><small>Perfect Trading · edición {version}</small><h1>{title}</h1><p>{subtitle}</p></header>{''.join(sections)}<footer class="proof">Release SHA-256: {checksum}</footer></main></body></html>"""
    return html.encode("utf-8")
