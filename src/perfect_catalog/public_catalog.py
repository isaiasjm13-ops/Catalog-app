"""Genera un catálogo HTML autónomo a partir de un Excel + fotos sueltas, sin abrir
ninguna conexión a la base de datos del operador.

Reutiliza exclusivamente las piezas puras del sistema (`prepare_rows`,
`exact_image_candidates`, `generate_catalog_html`, `_validate_logo`, `_validate_odoo`):
ninguna de ellas consulta ni escribe `product_reference`/`company`/`brand`, así que un
Excel que reutilice un SKU ya existente en el catálogo real simplemente no puede chocar
con nada — este módulo nunca compara contra el catálogo real.
"""

from __future__ import annotations

import hashlib
import tempfile
import uuid
from collections import Counter
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable

from PIL import Image as PILImage

from tools.odoo_profiler import read_tabular_source

from .brand_profiles import COLOR_PATTERN
from .catalog_exports import generate_catalog_html
from .image_archive_index import normalize_image_key
from .image_match_review import exact_image_candidates
from .importer import (
    DEFAULT_MAX_PILOT_ROWS,
    PreparedRow,
    analyze_headers,
    prepare_rows,
    validate_pilot_row_count,
)
from .intake import IMAGE_EXTENSIONS, _validate_odoo
from .visual_identities import _validate_logo

MAX_PUBLIC_EXCEL_BYTES = 32 * 1024 * 1024
MAX_PUBLIC_IMAGE_FILES = 500
MAX_PUBLIC_IMAGE_FILE_BYTES = 15 * 1024 * 1024
MAX_PUBLIC_IMAGE_TOTAL_BYTES = 300 * 1024 * 1024

_REFERENCE_NAMESPACE = uuid.UUID("2f6b6e6a-2f1a-4b6d-9d1a-1f6c6b6e6a2f")
_IMAGE_ENTRY_NAMESPACE = uuid.UUID("7a1c6e2b-4d3f-4b2a-8e9c-3b6a2f6e1c7a")


@dataclass(frozen=True)
class PublicCatalogResult:
    html: bytes
    product_count: int
    image_count: int
    matched_image_count: int
    ambiguous_image_count: int
    unmatched_image_count: int
    excel_sha256: str


def _require_text(value: str, field: str, *, max_length: int = 200) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} es obligatorio.")
    if len(text) > max_length:
        raise ValueError(f"{field} no puede superar {max_length} caracteres.")
    return text


def _require_color(value: str, field: str) -> str:
    text = str(value or "").strip().upper()
    if not COLOR_PATTERN.fullmatch(text):
        raise ValueError(f"{field} debe ser un color hexadecimal de 6 dígitos, p. ej. #112233.")
    return text


def _unique_preserve(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _application_label(application: dict[str, Any]) -> str:
    parts: list[Any] = [application.get("vehicle_brand"), application.get("model_suggestion")]
    years = application.get("years") or {}
    start, end = years.get("from"), years.get("to")
    if start and end and start != end:
        parts.append(f"{start}-{end}")
    elif start:
        parts.append(str(start))
    return " ".join(str(part) for part in parts if part)


def _catalog_row(prepared: PreparedRow) -> dict[str, Any]:
    """Adapta `PreparedRow.normalized` (Excel puro, ver `importer.prepare_rows`) a la
    forma plana que consume `generate_catalog_html`. Es el mismo análisis de nombre
    (`parse_product_name`) que ya usa el modo simple interno para auto-aprobar hasta
    500 productos sin revisión humana; aquí se aplica con la misma tolerancia."""
    normalized = prepared.normalized
    enrichment = normalized["name_enrichment"]
    applications = enrichment.get("applications") or []
    return {
        "internal_reference_original": normalized["internal_reference_original"],
        "internal_reference_normalized": normalized["internal_reference_normalized"],
        "name_original": normalized["name_original"],
        "category_path": normalized.get("category_path"),
        "brand": normalized.get("brand"),
        "applications": [
            label for label in (_application_label(item) for item in applications) if label
        ],
        "engine_types": _unique_preserve(
            item.get("evidence") for item in enrichment.get("engine_suggestions") or []
        ),
        "oem_references": list(enrichment.get("oem_references") or []),
        "fmsi_references": list(enrichment.get("fmsi_references") or []),
        "additional_references": list(enrichment.get("additional_references") or []),
        "vehicle_makes": _unique_preserve(item.get("vehicle_brand") for item in applications),
        "image_path": None,
        "variant_image_paths": [],
    }


def _safe_filename(filename: str, seen: set[str]) -> str:
    name = Path(str(filename or "")).name.strip() or "imagen"
    candidate = name
    suffix = 1
    while candidate in seen:
        stem, dot, extension = name.rpartition(".")
        candidate = f"{stem}-{suffix}.{extension}" if dot else f"{name}-{suffix}"
        suffix += 1
    seen.add(candidate)
    return candidate


def _validate_image_file(filename: str, content: bytes) -> None:
    suffix = Path(filename).suffix.lower()
    if suffix not in IMAGE_EXTENSIONS:
        raise ValueError(f"Formato de imagen no admitido: {filename!r}.")
    if not content or len(content) > MAX_PUBLIC_IMAGE_FILE_BYTES:
        raise ValueError(f"La imagen {filename!r} está vacía o supera el límite por archivo.")
    try:
        with PILImage.open(BytesIO(content)) as image:
            image.verify()
    except Exception as exc:
        raise ValueError(f"La imagen {filename!r} no es un archivo de imagen válido.") from exc


def _match_images(
    rows: list[dict[str, Any]], images: list[tuple[str, bytes]], bundle_dir: Path,
) -> tuple[int, int]:
    """Empareja fotos↔SKU en memoria (mismo algoritmo que el operador usa para fotos ya
    aprobadas, `image_match_review.exact_image_candidates`), pero contra las referencias
    del propio Excel — nunca contra el catálogo real. Devuelve (emparejadas, ambiguas).
    Escribe en `bundle_dir` sólo las fotos que sí se van a usar."""
    seen_names: set[str] = set()
    keyed: list[tuple[str, bytes, str]] = []
    for filename, content in images:
        _validate_image_file(filename, content)
        keyed.append((filename, content, normalize_image_key(filename)))
    key_counts = Counter(key for _, _, key in keyed)

    entries: list[dict[str, Any]] = []
    entry_files: dict[str, tuple[str, bytes]] = {}
    ambiguous = 0
    for filename, content, key in keyed:
        if key_counts[key] > 1:
            # Dos fotos distintas normalizan a la misma clave: evidencia contradictoria,
            # igual que en la revisión interna no se adivina, se deja sin vincular.
            ambiguous += 1
            continue
        entry_id = str(uuid.uuid5(_IMAGE_ENTRY_NAMESPACE, f"{filename}:{hashlib.sha256(content).hexdigest()}"))
        entries.append({
            "image_archive_entry_id": entry_id,
            "content_sha256": hashlib.sha256(content).hexdigest(),
            "lookup_key": key,
        })
        entry_files[entry_id] = (filename, content)

    references: list[dict[str, Any]] = []
    rows_by_reference: dict[str, dict[str, Any]] = {}
    for row in rows:
        reference_id = str(uuid.uuid5(_REFERENCE_NAMESPACE, str(row["internal_reference_normalized"])))
        rows_by_reference[reference_id] = row
        references.append({
            "product_reference_id": reference_id,
            "product_template_id": reference_id,
            "product_variant_id": None,
            "value_original": row["internal_reference_original"],
            "value_normalized": row["internal_reference_normalized"],
        })

    candidates = exact_image_candidates(entries, references)
    matched_entry_ids: set[str] = set()
    for candidate in candidates:
        row = rows_by_reference.get(candidate["product_reference_id"])
        entry = entry_files.get(candidate["image_archive_entry_id"])
        if row is None or entry is None:
            continue
        matched_entry_ids.add(candidate["image_archive_entry_id"])
        filename, content = entry
        stored_name = _safe_filename(filename, seen_names)
        (bundle_dir / stored_name).write_bytes(content)
        if candidate["variant_index"] is None and not row["image_path"]:
            row["image_path"] = stored_name
        else:
            row["variant_image_paths"].append(stored_name)
    return len(matched_entry_ids), ambiguous


def generate_public_catalog(
    *,
    excel_bytes: bytes,
    excel_filename: str,
    images: list[tuple[str, bytes]],
    company_name: str,
    brand_name: str,
    primary_color: str,
    secondary_color: str,
    ink_color: str = "#111111",
    paper_color: str = "#FFFFFF",
    logo: tuple[str, bytes] | None = None,
    max_rows: int = DEFAULT_MAX_PILOT_ROWS,
) -> PublicCatalogResult:
    company_name = _require_text(company_name, "company_name")
    brand_name = _require_text(brand_name, "brand_name", max_length=120)
    primary_color = _require_color(primary_color, "primary_color")
    secondary_color = _require_color(secondary_color, "secondary_color")
    ink_color = _require_color(ink_color, "ink_color")
    paper_color = _require_color(paper_color, "paper_color")
    if not excel_bytes or len(excel_bytes) > MAX_PUBLIC_EXCEL_BYTES:
        raise ValueError("El Excel está vacío o supera el límite de tamaño permitido.")
    extension = Path(excel_filename).suffix.lower()
    if extension not in {".xlsx", ".csv", ".tsv"}:
        raise ValueError("El archivo de productos debe ser .xlsx, .csv o .tsv.")
    if len(images) > MAX_PUBLIC_IMAGE_FILES:
        raise ValueError(f"Se admiten como máximo {MAX_PUBLIC_IMAGE_FILES:,} fotos por catálogo.")
    if sum(len(content) for _, content in images) > MAX_PUBLIC_IMAGE_TOTAL_BYTES:
        raise ValueError("El conjunto de fotos supera el límite total permitido.")

    excel_sha256 = hashlib.sha256(excel_bytes).hexdigest()

    with tempfile.TemporaryDirectory(prefix="public-catalog-") as tmp:
        tmp_dir = Path(tmp)
        excel_path = tmp_dir / f"excel{extension}"
        excel_path.write_bytes(excel_bytes)
        _validate_odoo(excel_path, extension)

        sheets = read_tabular_source(excel_path)
        if len(sheets) != 1 or not sheets[0].rows:
            raise ValueError("El archivo debe contener exactamente una hoja con datos.")
        sheet = sheets[0]
        headers = analyze_headers(sheet.rows[0]).headers
        prepared = prepare_rows(
            sheet.name, headers, sheet.rows[1:], sheet.row_numbers[1:], brand=brand_name,
        )
        validate_pilot_row_count(len(prepared), max_rows)

        rows = [_catalog_row(row) for row in prepared]
        bundle_dir = tmp_dir / "bundle"
        bundle_dir.mkdir()
        matched_count, ambiguous_count = _match_images(rows, images, bundle_dir)

        logo_relpath: str | None = None
        if logo is not None:
            logo_filename, logo_content = logo
            _media_type, logo_extension = _validate_logo(logo_filename, logo_content)
            logo_relpath = f"logo.{logo_extension}"
            (bundle_dir / logo_relpath).write_bytes(logo_content)

        config = {
            "template_profile": "T4",
            "title": f"Catálogo · {company_name}",
            "visual_profile": {
                "primary_color": primary_color,
                "secondary_color": secondary_color,
                "ink_color": ink_color,
                "paper_color": paper_color,
                "company": {
                    "display_name": company_name,
                    "primary_color": primary_color,
                    "secondary_color": secondary_color,
                    "ink_color": ink_color,
                    "paper_color": paper_color,
                    "packaged_logo_path": logo_relpath,
                },
            },
        }
        html = generate_catalog_html(rows, config, bundle_dir=bundle_dir, embed_images=True)

    return PublicCatalogResult(
        html=html,
        product_count=len(rows),
        image_count=len(images),
        matched_image_count=matched_count,
        ambiguous_image_count=ambiguous_count,
        unmatched_image_count=max(len(images) - matched_count - ambiguous_count, 0),
        excel_sha256=excel_sha256,
    )
