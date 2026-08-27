from __future__ import annotations

import io
import csv
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
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .releases import release_snapshot_sha256, validate_release_definition, validate_release_items

THEME_PALETTES = {
    "forest": {"primary": "#086650", "ink": "#17231F", "paper": "#F4F1E8", "card": "#FFFFFF"},
    "industrial": {"primary": "#C34A21", "ink": "#22272B", "paper": "#ECEBE7", "card": "#FFFFFF"},
    "midnight": {"primary": "#2E63C7", "ink": "#111827", "paper": "#E9EEF7", "card": "#FFFFFF"},
    "classic": {"primary": "#8A6A2F", "ink": "#211D17", "paper": "#F5F0E5", "card": "#FFFDF8"},
}
CATALOG_THEMES = tuple(THEME_PALETTES)


def _theme(config: dict[str, Any]) -> dict[str, str]:
    return THEME_PALETTES.get(str(config.get("theme") or "forest"), THEME_PALETTES["forest"])


def export_rows_from_release(release: dict[str, Any], items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Adapta exclusivamente un release completo cuya integridad criptográfica fue revalidada."""
    materialized = sorted(list(items), key=lambda item: item["item_order"])
    validate_release_definition(release["definition"], len(materialized))
    validate_release_items(materialized)
    calculated = release_snapshot_sha256(uuid.UUID(str(release["brand_id"])), str(release["version"]), release["definition"], materialized)
    if calculated != release["snapshot_sha256"]:
        raise ValueError("Los items no coinciden con snapshot_sha256 del release.")
    rows = [dict(item["snapshot_data"]) for item in materialized]
    for row in rows:
        for excluded in ("quantity_available", "quantity_on_hand", "uom_original", "currency", "price", "price_two"):
            row.pop(excluded, None)
    return rows


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
    if row.get("category_path"):
        parts.append("Categoría: " + escape(str(row["category_path"])))
    if row.get("brand"):
        parts.append("Marca: " + escape(str(row["brand"])))
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
    *, bundle_dir: Path | None = None, release: dict[str, Any] | None = None,
) -> bytes:
    config = config or {}
    release = release or {}
    columns = max(1, min(3, int(config.get("columns_per_row", 2))))
    title = str(config.get("title") or "Catálogo de productos")
    palette = _theme(config)
    styles = getSampleStyleSheet()
    cover_title_style = ParagraphStyle(
        "PerfectCatalogCoverTitle", parent=styles["Title"],
        textColor=colors.HexColor(palette["primary"]), fontName="Helvetica-Bold",
        fontSize=32, leading=36, alignment=TA_CENTER, spaceAfter=14,
    )
    cover_subtitle_style = ParagraphStyle(
        "PerfectCatalogCoverSubtitle", parent=styles["Heading2"],
        textColor=colors.HexColor(palette["ink"]), fontName="Helvetica",
        fontSize=15, leading=20, alignment=TA_CENTER,
    )
    section_style = ParagraphStyle(
        "PerfectCatalogSection", parent=styles["Heading1"],
        textColor=colors.HexColor(palette["primary"]), fontName="Helvetica-Bold",
    )
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title=title, leftMargin=1.2*cm, rightMargin=1.2*cm)
    story: list[Any] = [
        Spacer(1, 6 * cm), Paragraph(escape(title), cover_title_style),
        Paragraph(escape(str(config.get("subtitle") or "")), cover_subtitle_style), PageBreak(),
    ]
    for section, section_rows in _groups(
        rows, str(config.get("group_by") or "category_path"),
        str(config["group_by_secondary"]) if config.get("group_by_secondary") else None,
    ):
        story.extend([Paragraph(escape(section), section_style), Spacer(1, .25*cm)])
        cells = [_pdf_cell(row, styles, bundle_dir) for row in section_rows]
        grid = [cells[index:index+columns] for index in range(0, len(cells), columns)]
        if grid and len(grid[-1]) < columns:
            grid[-1].extend([""] * (columns-len(grid[-1])))
        table = Table(grid, colWidths=[(A4[0]-2.4*cm)/columns]*columns, repeatRows=0)
        table.setStyle(TableStyle([("BOX", (0,0), (-1,-1), .5, colors.HexColor(palette["primary"])), ("INNERGRID", (0,0), (-1,-1), .25, colors.lightgrey), ("VALIGN", (0,0), (-1,-1), "TOP"), ("PADDING", (0,0), (-1,-1), 8)]))
        story.extend([table, Spacer(1, .4*cm)])
    def decorate(canvas: Any, document: Any) -> None:
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor(palette["primary"]))
        canvas.setLineWidth(2)
        canvas.line(1.2 * cm, A4[1] - .8 * cm, A4[0] - 1.2 * cm, A4[1] - .8 * cm)
        canvas.setFillColor(colors.HexColor(palette["ink"]))
        canvas.setFont("Helvetica", 7)
        version = str(release.get("version") or "")
        checksum = str(release.get("snapshot_sha256") or "")[:16]
        proof = " · ".join(value for value in (version, checksum) if value)
        canvas.drawString(1.2 * cm, .65 * cm, proof)
        canvas.drawRightString(A4[0] - 1.2 * cm, .65 * cm, f"Página {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return buffer.getvalue()


def generate_catalog_pptx(
    rows: list[dict[str, Any]], config: dict[str, Any] | None = None,
    *, bundle_dir: Path | None = None, release: dict[str, Any] | None = None,
) -> bytes:
    config = config or {}
    release = release or {}
    columns = max(1, min(3, int(config.get("columns_per_row", 2))))
    title = str(config.get("title") or "Catálogo de productos")
    palette = _theme(config)
    primary_rgb = RGBColor.from_string(palette["primary"].lstrip("#"))
    prs = Presentation()
    cover = prs.slides.add_slide(prs.slide_layouts[0])
    cover.background.fill.solid(); cover.background.fill.fore_color.rgb = RGBColor.from_string(palette["paper"].lstrip("#"))
    cover.shapes.title.text = title
    cover.shapes.title.text_frame.paragraphs[0].font.color.rgb = primary_rgb
    proof = " · ".join(value for value in (
        str(config.get("subtitle") or ""), str(release.get("version") or ""),
        str(release.get("snapshot_sha256") or "")[:16],
    ) if value)
    cover.placeholders[1].text = proof
    cover.placeholders[1].text_frame.paragraphs[0].font.color.rgb = RGBColor.from_string(palette["ink"].lstrip("#"))
    per_slide = columns * 3
    for section, section_rows in _groups(
        rows, str(config.get("group_by") or "category_path"),
        str(config["group_by_secondary"]) if config.get("group_by_secondary") else None,
    ):
        for start in range(0, len(section_rows), per_slide):
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            slide.background.fill.solid(); slide.background.fill.fore_color.rgb = RGBColor.from_string(palette["paper"].lstrip("#"))
            heading = slide.shapes.add_textbox(Inches(.4), Inches(.2), Inches(12.5), Inches(.5))
            heading.text_frame.paragraphs[0].text = section
            heading.text_frame.paragraphs[0].font.size = Pt(22)
            heading.text_frame.paragraphs[0].font.bold = True
            heading.text_frame.paragraphs[0].font.color.rgb = primary_rgb
            for index, row in enumerate(section_rows[start:start+per_slide]):
                col, line = index % columns, index // columns
                width = 12.4 / columns
                box = slide.shapes.add_textbox(Inches(.4+col*width), Inches(.9+line*2.05), Inches(width-.15), Inches(1.85))
                box.fill.solid(); box.fill.fore_color.rgb = RGBColor.from_string(palette["card"].lstrip("#"))
                box.line.color.rgb = primary_rgb
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
                if row.get("category_path") or row.get("brand"):
                    metadata = " · ".join(str(value) for value in (row.get("category_path"), row.get("brand")) if value)
                    p = frame.add_paragraph(); p.text = metadata; p.font.size = Pt(8)
                if row.get("oem_references"):
                    p = frame.add_paragraph(); p.text = "OEM: " + ", ".join(map(str, row["oem_references"])); p.font.size = Pt(8)
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
    palette = _theme(config)
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
            category = escape(str(row.get("category_path") or ""))
            brand = escape(str(row.get("brand") or ""))
            oem = escape(", ".join(map(str, row.get("oem_references") or [])))
            cards.append(
                '<article class="product">' + image
                + f'<code>{escape(str(row.get("internal_reference_original") or "Sin referencia"))}</code>'
                + f'<h3>{escape(str(row.get("name_original") or "Sin nombre"))}</h3>'
                + (f'<p class="meta">{category}{" · " if category and brand else ""}{brand}</p>' if category or brand else "")
                + (f'<p><b>OEM:</b> {oem}</p>' if oem else "")
                + (f'<p><b>Aplicaciones:</b> {applications}</p>' if applications else "") + "</article>"
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
:root{{--ink:{palette['ink']};--forest:{palette['primary']};--paper:{palette['paper']};--card:{palette['card']};--line:#d9d5c9}}*{{box-sizing:border-box}}body{{margin:0;color:var(--ink);background:var(--paper);font:15px/1.5 Arial,sans-serif}}main{{max-width:1280px;margin:auto;padding:clamp(24px,5vw,72px)}}.hero{{min-height:45vh;display:grid;align-content:end;padding:8vw 0 4vw;border-bottom:4px solid var(--ink)}}.hero small{{color:var(--forest);font-weight:800;letter-spacing:.16em;text-transform:uppercase}}h1{{max-width:900px;margin:.2em 0;font:500 clamp(44px,8vw,104px)/.9 Georgia,serif}}.hero p{{max-width:700px;font-size:18px}}section{{padding:45px 0}}section>header{{display:flex;justify-content:space-between;gap:20px;align-items:end;border-bottom:1px solid var(--line)}}h2{{font:500 clamp(27px,4vw,48px) Georgia,serif}}section>header span{{padding-bottom:1.2em;color:#65716b}}.products{{display:grid;grid-template-columns:repeat({columns},minmax(0,1fr));gap:18px;padding-top:22px}}.product{{min-width:0;padding:18px;background:var(--card);border:1px solid var(--line)}}.photo{{height:190px;margin:-18px -18px 18px;background:#f8f8f5;display:grid;place-items:center;overflow:hidden}}.photo img{{width:100%;height:100%;object-fit:contain}}code{{color:var(--forest);font-weight:800}}h3{{margin:.5em 0;font:500 22px/1.15 Georgia,serif}}.proof{{padding:24px 0;border-top:1px solid var(--line);overflow-wrap:anywhere;color:#65716b;font-size:12px}}@media(max-width:760px){{.products{{grid-template-columns:1fr}}.hero{{min-height:35vh}}}}
</style></head><body><main><header class="hero"><small>Perfect Trading · edición {version}</small><h1>{title}</h1><p>{subtitle}</p></header>{''.join(sections)}<footer class="proof">Release SHA-256: {checksum}</footer></main></body></html>"""
    return html.encode("utf-8")


def generate_indesign_datamerge_csv(rows: list[dict[str, Any]]) -> bytes:
    """CSV UTF-8 BOM para Data Merge, sin fórmulas interpretables al abrirlo en hojas de cálculo."""
    def cell(value: object) -> str:
        if isinstance(value, (list, tuple)):
            text = "; ".join(str(item) for item in value)
        else:
            text = "" if value is None else str(value)
        return "'" + text if text.startswith(("=", "+", "-", "@")) else text

    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\r\n")
    writer.writerow(("reference", "name", "category", "brand", "applications", "oem_references", "@image"))
    for row in rows:
        writer.writerow((
            cell(row.get("internal_reference_original")), cell(row.get("name_original")),
            cell(row.get("category_path")), cell(row.get("brand")),
            cell(row.get("applications")), cell(row.get("oem_references")),
            cell(row.get("image_path")),
        ))
    return stream.getvalue().encode("utf-8-sig")
