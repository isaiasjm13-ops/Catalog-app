from __future__ import annotations

import io
import uuid
from collections import defaultdict
from html import escape
from typing import Any, Iterable

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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


def generate_catalog_pdf(rows: list[dict[str, Any]], config: dict[str, Any] | None = None) -> bytes:
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
        cells = [Paragraph(_detail(row), styles["BodyText"]) for row in section_rows]
        grid = [cells[index:index+columns] for index in range(0, len(cells), columns)]
        if grid and len(grid[-1]) < columns:
            grid[-1].extend([""] * (columns-len(grid[-1])))
        table = Table(grid, colWidths=[(A4[0]-2.4*cm)/columns]*columns, repeatRows=0)
        table.setStyle(TableStyle([("BOX", (0,0), (-1,-1), .5, colors.HexColor(config.get("primary_color", "#1B3A6B"))), ("INNERGRID", (0,0), (-1,-1), .25, colors.lightgrey), ("VALIGN", (0,0), (-1,-1), "TOP"), ("PADDING", (0,0), (-1,-1), 8)]))
        story.extend([table, Spacer(1, .4*cm)])
    doc.build(story)
    return buffer.getvalue()


def generate_catalog_pptx(rows: list[dict[str, Any]], config: dict[str, Any] | None = None) -> bytes:
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
                p = frame.paragraphs[0]; p.text = str(row.get("internal_reference_original") or ""); p.font.bold = True; p.font.size = Pt(12)
                p = frame.add_paragraph(); p.text = str(row.get("name_original") or ""); p.font.size = Pt(11)
                if row.get("applications"):
                    p = frame.add_paragraph(); p.text = "Aplicaciones: " + "; ".join(map(str, row["applications"])); p.font.size = Pt(8)
    output = io.BytesIO(); prs.save(output)
    return output.getvalue()
