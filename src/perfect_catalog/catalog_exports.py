from __future__ import annotations

import io
import csv
import uuid
from collections import defaultdict
from html import escape
from importlib.resources import files
from pathlib import Path
from typing import Any, Iterable

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .releases import release_snapshot_sha256, validate_release_definition, validate_release_items

THEME_PALETTES = {
    "forest": {"primary": "#086650", "ink": "#17231F", "paper": "#F4F1E8", "card": "#FFFFFF"},
    "industrial": {"primary": "#C34A21", "ink": "#22272B", "paper": "#ECEBE7", "card": "#FFFFFF"},
    "midnight": {"primary": "#2E63C7", "ink": "#111827", "paper": "#E9EEF7", "card": "#FFFFFF"},
    "classic": {"primary": "#8A6A2F", "ink": "#211D17", "paper": "#F5F0E5", "card": "#FFFDF8"},
}
CATALOG_THEMES = tuple(THEME_PALETTES)
NATSUKI_TITLE_FONT = "BarlowCondensed-Bold"
NATSUKI_BODY_FONT = "DMSans-Regular"
NATSUKI_BODY_BOLD_FONT = "DMSans-Bold"
MINIMUM_CATALOG_FONT_SIZE = 12


def _register_natsuki_fonts() -> None:
    font_root = files("perfect_catalog").joinpath("assets/brands/natsuki/fonts")
    for name, filename in (
        (NATSUKI_TITLE_FONT, "BarlowCondensed-Bold.ttf"),
        (NATSUKI_BODY_FONT, "DMSans-Regular.ttf"),
        (NATSUKI_BODY_BOLD_FONT, "DMSans-Bold.ttf"),
    ):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(font_root.joinpath(filename))))


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
        primary_values = (
            row.get("vehicle_makes") or ["Sin marca vehicular"]
            if key == "vehicle_make" else [row.get(key) or "Sin categoría"]
        )
        secondary_values = (
            row.get("vehicle_makes") or ["Sin marca vehicular"]
            if secondary_key == "vehicle_make" else [row.get(secondary_key) or "Sin subgrupo"]
            if secondary_key else [""]
        )
        for primary in primary_values:
            for secondary in secondary_values:
                label = f"{primary} · {secondary}" if secondary else str(primary)
                grouped[label].append(row)
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


def _pdf_cell(
    row: dict[str, Any], styles: Any, bundle_dir: Path | None,
    palette: dict[str, str], columns: int,
) -> list[Any]:
    contents: list[Any] = []
    image_path = _safe_bundle_image(row, bundle_dir)
    if image_path:
        try:
            width, height = ImageReader(str(image_path)).getSize()
            available_width = (A4[0] - 3.2 * cm) / columns
            scale = min(available_width / width, (4.4 if columns == 1 else 3.2) * cm / height)
            product_image = Image(str(image_path), width=width * scale, height=height * scale)
            product_image.hAlign = "CENTER"
            contents.extend([product_image, Spacer(1, .22 * cm)])
        except Exception:
            pass
    reference = escape(str(row.get("internal_reference_original") or "Sin referencia"))
    contents.append(Paragraph(reference, styles["CatalogReference"]))
    contents.append(Paragraph(escape(str(row.get("name_original") or "Sin nombre")), styles["CatalogProductTitle"]))
    detail_parts: list[str] = []
    if row.get("category_path"):
        detail_parts.append(escape(str(row["category_path"])))
    if row.get("applications"):
        detail_parts.append("<b>Aplicaciones</b><br/>" + escape("; ".join(map(str, row["applications"]))))
    if row.get("oem_references"):
        detail_parts.append("<b>OEM</b> · " + escape(", ".join(map(str, row["oem_references"]))))
    if detail_parts:
        contents.append(Paragraph("<br/>".join(detail_parts), styles["CatalogMeta"]))
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
    _register_natsuki_fonts()
    styles = getSampleStyleSheet()
    cover_title_style = ParagraphStyle(
        "PerfectCatalogCoverTitle", parent=styles["Title"],
        textColor=colors.HexColor(palette["ink"]), fontName=NATSUKI_TITLE_FONT,
        fontSize=38, leading=41, alignment=0, spaceAfter=14,
    )
    cover_subtitle_style = ParagraphStyle(
        "PerfectCatalogCoverSubtitle", parent=styles["Heading2"],
        textColor=colors.HexColor(palette["ink"]), fontName=NATSUKI_BODY_FONT,
        fontSize=15, leading=20, alignment=0,
    )
    section_style = ParagraphStyle(
        "PerfectCatalogSection", parent=styles["Heading1"],
        textColor=colors.HexColor(palette["ink"]), fontName=NATSUKI_TITLE_FONT,
        fontSize=23, leading=27, spaceAfter=4,
    )
    styles.add(ParagraphStyle(
        "CatalogEyebrow", parent=styles["Normal"], textColor=colors.HexColor(palette["primary"]),
        fontName=NATSUKI_BODY_BOLD_FONT, fontSize=12, leading=21.6, spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        "CatalogReference", parent=styles["Normal"], textColor=colors.HexColor(palette["primary"]),
        fontName=NATSUKI_BODY_BOLD_FONT, fontSize=12, leading=21.6, spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        "CatalogProductTitle", parent=styles["Heading3"], textColor=colors.HexColor(palette["ink"]),
        fontName=NATSUKI_TITLE_FONT, fontSize=14,
        leading=22, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        "CatalogMeta", parent=styles["BodyText"], textColor=colors.HexColor("#56645e"),
        fontName=NATSUKI_BODY_FONT, fontSize=12,
        leading=21.6,
    ))
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, title=title, author="Perfect Trading",
        subject="Catálogo verificable de productos",
        leftMargin=1.35*cm, rightMargin=1.35*cm, topMargin=1.55*cm, bottomMargin=1.35*cm,
    )
    version = str(release.get("version") or "Edición de trabajo")
    checksum = str(release.get("snapshot_sha256") or "")
    cover_meta = Table(
        [[Paragraph("EDICIÓN", styles["CatalogEyebrow"]), Paragraph("PRODUCTOS", styles["CatalogEyebrow"]), Paragraph("IDENTIDAD", styles["CatalogEyebrow"])],
         [Paragraph(escape(version), styles["BodyText"]), Paragraph(str(len(rows)), styles["BodyText"]), Paragraph(escape(checksum[:16] or "Sin publicar"), styles["BodyText"]) ]],
        colWidths=[6.2 * cm, 3.2 * cm, 7.4 * cm],
    )
    cover_meta.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1, colors.HexColor(palette["primary"])),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))
    story: list[Any] = [
        Spacer(1, 4.4 * cm), Paragraph("PERFECT TRADING · CATÁLOGO", styles["CatalogEyebrow"]),
        Paragraph(escape(title), cover_title_style),
        Paragraph(escape(str(config.get("subtitle") or "Selección técnica de productos")), cover_subtitle_style),
        Spacer(1, 2.2 * cm), cover_meta, PageBreak(),
    ]
    for section_index, (section, section_rows) in enumerate(_groups(
        rows, str(config.get("group_by") or "category_path"),
        str(config["group_by_secondary"]) if config.get("group_by_secondary") else None,
    )):
        cells = [_pdf_cell(row, styles, bundle_dir, palette, columns) for row in section_rows]
        page_capacity = {1: 2, 2: 4, 3: 6}[columns]
        chunks = [cells[index:index + page_capacity] for index in range(0, len(cells), page_capacity)]
        for chunk_index, chunk in enumerate(chunks):
            if section_index or chunk_index:
                story.append(PageBreak())
            continuation = " · CONTINUACIÓN" if chunk_index else ""
            story.extend([
                Paragraph(f"SECCIÓN {section_index + 1:02d}{continuation}", styles["CatalogEyebrow"]),
                Paragraph(escape(section), section_style),
                Paragraph(f"{len(section_rows)} productos", styles["CatalogMeta"]),
                HRFlowable(width="100%", thickness=1, color=colors.HexColor(palette["primary"]), spaceBefore=7, spaceAfter=12),
            ])
            grid = [chunk[index:index + columns] for index in range(0, len(chunk), columns)]
            if grid and len(grid[-1]) < columns:
                grid[-1].extend([""] * (columns - len(grid[-1])))
            table = Table(grid, colWidths=[(A4[0]-2.7*cm)/columns]*columns, repeatRows=0, hAlign="LEFT")
            table.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,-1), colors.HexColor(palette["card"])),
                ("BOX", (0,0), (-1,-1), .45, colors.HexColor("#d7ddd9")),
                ("INNERGRID", (0,0), (-1,-1), .35, colors.HexColor("#e3e7e4")),
                ("LINEABOVE", (0,0), (-1,0), 2, colors.HexColor(palette["primary"])),
                ("VALIGN", (0,0), (-1,-1), "TOP"), ("PADDING", (0,0), (-1,-1), 11),
            ]))
            story.extend([table, Spacer(1, .5*cm)])

    def decorate_cover(canvas: Any, document: Any) -> None:
        canvas.saveState()
        canvas.setFillColor(colors.HexColor(palette["paper"]))
        canvas.rect(0, 0, A4[0], A4[1], stroke=0, fill=1)
        canvas.setFillColor(colors.HexColor(palette["primary"]))
        canvas.rect(0, A4[1] - 1.1 * cm, A4[0], 1.1 * cm, stroke=0, fill=1)
        canvas.circle(A4[0] - 2.4 * cm, A4[1] - 3.5 * cm, 1.25 * cm, stroke=0, fill=1)
        canvas.restoreState()

    def decorate(canvas: Any, document: Any) -> None:
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor(palette["primary"]))
        canvas.setLineWidth(2)
        canvas.line(1.2 * cm, A4[1] - .8 * cm, A4[0] - 1.2 * cm, A4[1] - .8 * cm)
        canvas.setFillColor(colors.HexColor(palette["ink"]))
        canvas.setFont(NATSUKI_BODY_FONT, MINIMUM_CATALOG_FONT_SIZE)
        canvas.drawString(1.35 * cm, A4[1] - 1.15 * cm, title[:70])
        proof = " · ".join(value for value in (version, checksum[:16]) if value)
        canvas.drawString(1.2 * cm, .65 * cm, proof)
        canvas.drawRightString(A4[0] - 1.2 * cm, .65 * cm, f"Página {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=decorate_cover, onLaterPages=decorate)
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
:root{{--ink:{palette['ink']};--forest:{palette['primary']};--paper:{palette['paper']};--card:{palette['card']};--line:#d9d5c9;--muted:#65716b}}*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;color:var(--ink);background:var(--paper);font:15px/1.55 Arial,sans-serif}}main{{max-width:1280px;margin:auto;padding:clamp(24px,5vw,72px)}}.hero{{position:relative;min-height:48vh;display:grid;align-content:end;padding:8vw clamp(0px,2vw,28px) 4vw;border-bottom:4px solid var(--ink)}}.hero:before{{content:"";position:absolute;top:12%;right:2%;width:clamp(90px,14vw,190px);aspect-ratio:1;border:1px solid var(--forest);border-radius:50%;opacity:.22}}.hero small{{color:var(--forest);font-weight:800;letter-spacing:.16em;text-transform:uppercase}}h1{{position:relative;max-width:900px;margin:.2em 0;font:500 clamp(44px,8vw,104px)/.9 Georgia,serif;letter-spacing:-.035em}}.hero p{{max-width:700px;font-size:18px}}section{{padding:clamp(38px,6vw,72px) 0}}section>header{{display:flex;justify-content:space-between;gap:20px;align-items:end;border-bottom:1px solid var(--line)}}h2{{margin:.25em 0;font:500 clamp(27px,4vw,48px) Georgia,serif;letter-spacing:-.02em}}section>header span{{padding-bottom:1.2em;color:var(--muted)}}.products{{display:grid;grid-template-columns:repeat({columns},minmax(0,1fr));gap:20px;padding-top:24px}}.product{{min-width:0;padding:20px;background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:0 10px 30px rgba(20,42,34,.06);overflow:hidden}}.photo{{height:210px;margin:-20px -20px 20px;background:#f8f8f5;display:grid;place-items:center;overflow:hidden;border-bottom:1px solid var(--line)}}.photo img{{width:100%;height:100%;object-fit:contain}}code{{color:var(--forest);font-weight:800;letter-spacing:.035em}}h3{{margin:.5em 0;font:500 22px/1.15 Georgia,serif}}.meta{{color:var(--muted);font-size:13px}}.proof{{padding:28px 0;border-top:1px solid var(--line);overflow-wrap:anywhere;color:var(--muted);font-size:12px}}@media(max-width:760px){{html{{scroll-behavior:auto}}.products{{grid-template-columns:1fr}}.hero{{min-height:38vh}}section>header{{align-items:start;flex-direction:column;gap:0}}section>header span{{padding-bottom:1em}}}}
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
    writer.writerow(("reference", "name", "category", "brand", "vehicle_make", "applications", "oem_references", "@image"))
    for row in rows:
        writer.writerow((
            cell(row.get("internal_reference_original")), cell(row.get("name_original")),
            cell(row.get("category_path")), cell(row.get("brand")),
            cell(row.get("vehicle_make") or row.get("vehicle_makes")),
            cell(row.get("applications")), cell(row.get("oem_references")),
            cell(row.get("image_path")),
        ))
    return stream.getvalue().encode("utf-8-sig")
