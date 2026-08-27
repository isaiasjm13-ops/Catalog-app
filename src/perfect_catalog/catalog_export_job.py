from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
import io
import zipfile
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from typing import Any, Iterable

from .catalog_exports import CATALOG_THEMES, export_rows_from_release, generate_catalog_html, generate_catalog_pdf, generate_catalog_pptx, generate_indesign_datamerge_csv
from .config import DatabaseConfig
from .publication import load_published_release

INDESIGN_SNAPSHOT_SCHEMA = "perfect-catalog.indesign-snapshot.v1"
EXPORT_MANIFEST_SCHEMA = "perfect-catalog.export-manifest.v1"
EXPORT_VERIFICATION_SCHEMA = "perfect-catalog.export-verification.v1"
SUPPORTED_FORMATS = ("html", "html-standalone", "pdf", "pptx", "indesign-json")
DEFAULT_FORMATS = ("html", "pdf", "pptx", "indesign-json")
INDESIGN_TEMPLATE_PROFILES = ("T4", "T2", "T1", "TABLE")
INDESIGN_PRODUCTS_PER_PAGE = {"T4": 4, "T2": 2, "T1": 1, "TABLE": 10}
CATALOG_GROUP_FIELDS = ("category_path", "brand", "vehicle_make", "internal_reference_original")
CATALOG_FILTER_FIELDS = ("all", "category_path", "brand", "vehicle_make", "internal_reference_original", "name_original")
MAX_SELECTED_REFERENCES = 5000
MAX_INDESIGN_PREFLIGHT_BYTES = 1024 * 1024
INDESIGN_PREFLIGHT_SCHEMA = "perfect-catalog.indesign-preflight.v1"
INDESIGN_PREFLIGHT_RECEIPT_SCHEMA = "perfect-catalog.indesign-preflight-receipt.v1"


def estimate_indesign_layout(groups: Iterable[dict[str, Any]], template_profile: str) -> dict[str, Any]:
    profile = str(template_profile).upper()
    if profile not in INDESIGN_PRODUCTS_PER_PAGE:
        raise ValueError("Perfil InDesign no soportado.")
    counts: list[int] = []
    for group in groups:
        count = group.get("count") if isinstance(group, dict) else None
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            raise ValueError("La agrupación no permite estimar páginas InDesign.")
        counts.append(count)
    if not counts:
        raise ValueError("No hay grupos para estimar la composición InDesign.")
    per_page = INDESIGN_PRODUCTS_PER_PAGE[profile]
    product_pages = sum((count + per_page - 1) // per_page for count in counts)
    separator_pages = len(counts)
    return {
        "schema": "perfect-catalog.indesign-layout-estimate.v1",
        "template_profile": profile,
        "products_per_page": per_page,
        "cover_pages": 1,
        "separator_pages": separator_pages,
        "product_pages": product_pages,
        "estimated_page_count": 1 + separator_pages + product_pages,
    }


def record_indesign_preflight(
    output_root: Path, release_id: uuid.UUID, export_id: uuid.UUID,
    content: bytes, *, actor: str, reason: str,
) -> dict[str, Any]:
    if not content or len(content) > MAX_INDESIGN_PREFLIGHT_BYTES:
        raise ValueError("El preflight debe contener entre 1 byte y 1 MiB.")
    actor = str(actor).strip()
    reason = str(reason).strip()
    if not 1 <= len(actor) <= 200 or not 4 <= len(reason) <= 500:
        raise ValueError("Actor o motivo de preflight no válido.")
    try:
        report = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("El preflight no es JSON UTF-8 válido.") from exc
    expected_fields = {
        "schema", "release_id", "snapshot_sha256", "template_profile", "theme",
        "product_count", "linked_image_count", "missing_images",
        "overflow_product_indexes", "unavailable_fonts", "group_count", "page_count",
    }
    if not isinstance(report, dict) or set(report) != expected_fields:
        raise ValueError("El preflight no cumple el contrato exacto de InDesign.")
    if report["schema"] != INDESIGN_PREFLIGHT_SCHEMA or report["release_id"] != str(release_id):
        raise ValueError("El preflight no corresponde al release solicitado.")
    root = output_root.resolve()
    bundle = root / str(release_id) / str(export_id)
    manifests = list(bundle.glob("*.manifest.json")) if bundle.is_dir() else []
    if len(manifests) != 1:
        raise FileNotFoundError("La exportación no tiene un manifiesto único.")
    verify_catalog_bundle(manifests[0])
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    release = manifest["release"]
    layout = manifest.get("layout") or {}
    selection = manifest.get("selection") or {}
    expected_product_count = selection.get("selected_item_count", release.get("item_count"))
    if (
        report["snapshot_sha256"] != release.get("snapshot_sha256")
        or report["template_profile"] != layout.get("template_profile")
        or report["theme"] != layout.get("theme")
        or report["product_count"] != expected_product_count
    ):
        raise ValueError("El preflight no coincide con la exportación exacta.")
    product_count = report["product_count"]
    integer_fields = ("product_count", "linked_image_count", "group_count", "page_count")
    if any(not isinstance(report[field], int) or isinstance(report[field], bool) for field in integer_fields):
        raise ValueError("El preflight contiene conteos no válidos.")
    if product_count < 1 or not 0 <= report["linked_image_count"] <= product_count:
        raise ValueError("El preflight contiene conteos fuera de rango.")
    if report["group_count"] < 1 or report["page_count"] < 1 + report["group_count"]:
        raise ValueError("El preflight contiene una paginación imposible.")
    if not all(isinstance(report[field], list) for field in ("missing_images", "overflow_product_indexes", "unavailable_fonts")):
        raise ValueError("El preflight contiene listas no válidas.")
    indexes = report["overflow_product_indexes"]
    if any(not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < product_count for index in indexes):
        raise ValueError("El preflight contiene índices de overflow no válidos.")
    if len(indexes) != len(set(indexes)):
        raise ValueError("El preflight contiene índices de overflow duplicados.")
    if any(not isinstance(name, str) or not name or len(name) > 300 for name in report["unavailable_fonts"]):
        raise ValueError("El preflight contiene nombres de fuente no válidos.")
    missing_indexes: list[int] = []
    for item in report["missing_images"]:
        if not isinstance(item, dict) or set(item) != {"product_index", "reference", "reason"}:
            raise ValueError("El preflight contiene incidencias de imagen no válidas.")
        index = item["product_index"]
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < product_count:
            raise ValueError("El preflight contiene índices de imagen no válidos.")
        if any(not isinstance(item[field], str) or not item[field] or len(item[field]) > 500 for field in ("reference", "reason")):
            raise ValueError("El preflight contiene detalles de imagen no válidos.")
        missing_indexes.append(index)
    if len(missing_indexes) != len(set(missing_indexes)):
        raise ValueError("El preflight contiene incidencias de imagen duplicadas.")
    snapshot_entries = [item for item in manifest["files"] if item.get("format") == "indesign-json"]
    if len(snapshot_entries) != 1:
        raise ValueError("La exportación no contiene un snapshot InDesign único.")
    snapshot = json.loads((bundle / str(snapshot_entries[0]["filename"])).read_text(encoding="utf-8"))
    products = snapshot.get("products") if isinstance(snapshot, dict) else None
    snapshot_layout = snapshot.get("layout") if isinstance(snapshot, dict) else None
    if (
        snapshot.get("schema") != INDESIGN_SNAPSHOT_SCHEMA
        or not isinstance(products, list) or len(products) != product_count
        or not isinstance(snapshot_layout, dict)
    ):
        raise ValueError("El snapshot InDesign no permite validar la paginación.")
    group_by = str(snapshot_layout.get("group_by") or "category_path")
    secondary = str(snapshot_layout.get("group_by_secondary") or "")
    group_counts: dict[str, int] = {}
    for product in products:
        if not isinstance(product, dict):
            raise ValueError("El snapshot InDesign contiene un producto no válido.")
        primary_value = product.get(group_by)
        primary = str(primary_value) if primary_value not in (None, "") else "Sin categoría"
        label = primary
        if secondary:
            secondary_value = product.get(secondary)
            secondary_label = str(secondary_value) if secondary_value not in (None, "") else "Sin subgrupo"
            label += " · " + secondary_label
        group_counts[label] = group_counts.get(label, 0) + 1
    expected_layout = estimate_indesign_layout(
        [{"count": count} for count in group_counts.values()], report["template_profile"]
    )
    if (
        report["group_count"] != expected_layout["separator_pages"]
        or report["page_count"] != expected_layout["estimated_page_count"]
    ):
        raise ValueError("La paginación del preflight no coincide con el snapshot InDesign.")
    issue_counts = {
        "missing_images": len(report["missing_images"]),
        "overflows": len(report["overflow_product_indexes"]),
        "unavailable_fonts": len(report["unavailable_fonts"]),
    }
    quality_status = "passed" if not any(issue_counts.values()) else "issues"
    receipt_id = uuid.uuid4()
    receipt = {
        "schema": INDESIGN_PREFLIGHT_RECEIPT_SCHEMA,
        "receipt_id": str(receipt_id), "release_id": str(release_id),
        "export_id": str(export_id), "actor": actor, "reason": reason,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "source_bytes": len(content), "source_sha256": _sha256(content), "report": report,
        "quality": {"status": quality_status, "issue_counts": issue_counts, "expected_layout": expected_layout},
    }
    destination = root / "_indesign_preflight" / str(release_id) / str(export_id) / f"{receipt_id}.json"
    if not destination.resolve().is_relative_to(root):
        raise ValueError("Ruta de preflight no segura.")
    _write_new(destination, _json_bytes(receipt))
    return {**receipt, "path": str(destination)}


def list_indesign_preflight_receipts(output_root: Path, *, limit: int = 500) -> list[dict[str, Any]]:
    if not 1 <= limit <= 2000:
        raise ValueError("limit debe estar entre 1 y 2000.")
    root = output_root.resolve()
    receipt_root = root / "_indesign_preflight"
    if not receipt_root.is_dir():
        return []
    results: list[dict[str, Any]] = []
    for path in sorted(receipt_root.glob("*/*/*.json"), reverse=True):
        try:
            release_id = uuid.UUID(path.parent.parent.name)
            export_id = uuid.UUID(path.parent.name)
            receipt_id = uuid.UUID(path.stem)
            payload = json.loads(path.read_text(encoding="utf-8"))
            if (
                payload.get("schema") != INDESIGN_PREFLIGHT_RECEIPT_SCHEMA
                or payload.get("release_id") != str(release_id)
                or payload.get("export_id") != str(export_id)
                or payload.get("receipt_id") != str(receipt_id)
            ):
                continue
            results.append(payload)
        except (ValueError, OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if len(results) >= limit:
            break
    return results


def resolve_indesign_preflight_receipt(
    output_root: Path, release_id: uuid.UUID, export_id: uuid.UUID, receipt_id: uuid.UUID,
) -> Path:
    root = output_root.resolve()
    target = root / "_indesign_preflight" / str(release_id) / str(export_id) / f"{receipt_id}.json"
    target = target.resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise FileNotFoundError("El recibo de preflight no existe.")
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("El recibo de preflight no es válido.") from exc
    if (
        payload.get("schema") != INDESIGN_PREFLIGHT_RECEIPT_SCHEMA
        or payload.get("release_id") != str(release_id)
        or payload.get("export_id") != str(export_id)
        or payload.get("receipt_id") != str(receipt_id)
    ):
        raise ValueError("El recibo no corresponde a la exportación solicitada.")
    return target


def _safe_stem(value: object) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value)).strip("-._")
    return stem[:80] or "catalog"


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_new(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            raise FileExistsError(f"La exportación ya existe: {path}")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _digital_zip(
    html_content: bytes, image_files: list[dict[str, Any]], output_dir: Path
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        entries = [("index.html", html_content)]
        entries.extend(
            (str(item["filename"]), (output_dir / str(item["filename"])).read_bytes())
            for item in image_files
        )
        for filename, content in entries:
            info = zipfile.ZipInfo(filename, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    return buffer.getvalue()


def _indesign_zip(
    snapshot_content: bytes, datamerge_content: bytes,
    image_files: list[dict[str, Any]], output_dir: Path,
    config: dict[str, Any],
) -> bytes:
    script_path = Path(__file__).resolve().parents[2] / "indesign" / "ImportPerfectCatalog.jsx"
    if not script_path.is_file():
        raise RuntimeError("No está disponible el puente InDesign del proyecto.")
    instructions = (
        "PERFECT CATALOG - PAQUETE INDESIGN\r\n\r\n"
        "1. Extrae todo el ZIP conservando los archivos juntos.\r\n"
        "2. Abre Adobe InDesign.\r\n"
        "3. Ejecuta ImportPerfectCatalog.jsx desde Ventana > Utilidades > Scripts.\r\n"
        "4. El script detecta catalog.indesign.json y solicita dónde guardar el INDD.\r\n"
        "5. Revisa el archivo .preflight.json generado junto al INDD.\r\n"
        "6. El documento se compone en A4 vertical, paginas no enfrentadas y sangrado uniforme de 3 mm.\r\n"
        "Alternativa: usa catalog.datamerge.csv desde Ventana > Utilidades > Combinación de datos.\r\n"
    ).encode("utf-8")
    entries = [
        ("catalog.indesign.json", snapshot_content),
        ("catalog.datamerge.csv", datamerge_content),
        ("ImportPerfectCatalog.jsx", script_path.read_bytes()),
        ("LEEME-INDESIGN.txt", instructions),
    ]
    if (config.get("visual_profile") or {}).get("logo_asset_key") == "brands/natsuki/logo.svg":
        assets = files("perfect_catalog").joinpath("assets/brands/natsuki")
        entries.extend([
            ("brand/logo.svg", assets.joinpath("logo.svg").read_bytes()),
            ("brand/logo.png", assets.joinpath("logo.png").read_bytes()),
            ("Document fonts/BarlowCondensed-Regular.ttf", assets.joinpath("fonts/BarlowCondensed-Regular.ttf").read_bytes()),
            ("Document fonts/BarlowCondensed-Bold.ttf", assets.joinpath("fonts/BarlowCondensed-Bold.ttf").read_bytes()),
            ("Document fonts/DMSans-Regular.ttf", assets.joinpath("fonts/DMSans-Regular.ttf").read_bytes()),
            ("Document fonts/DMSans-Bold.ttf", assets.joinpath("fonts/DMSans-Bold.ttf").read_bytes()),
        ])
    entries.extend(
        (str(item["filename"]), (output_dir / str(item["filename"])).read_bytes())
        for item in image_files
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for filename, content in entries:
            info = zipfile.ZipInfo(filename, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    return buffer.getvalue()


def _package_images(
    rows: list[dict[str, Any]], output_dir: Path, image_root: Path | None
) -> list[dict[str, Any]]:
    image_rows = [row for row in rows if row.get("image_storage_relpath")]
    if not image_rows:
        return []
    if image_root is None:
        raise RuntimeError("El release contiene imágenes pero no se configuró image_root.")
    root = image_root.resolve()
    packaged: dict[str, dict[str, Any]] = {}
    for row in image_rows:
        digest = str(row.get("image_sha256") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise RuntimeError("Una imagen materializada no conserva un SHA-256 válido.")
        relative = Path(str(row["image_storage_relpath"]))
        source = (root / relative).resolve()
        if not source.is_relative_to(root) or not source.is_file():
            raise RuntimeError("Una imagen materializada falta o sale de image_root.")
        suffix = source.suffix.lower()
        # Keep deliverables flat: the operator download route deliberately accepts
        # only manifest-approved basenames, which avoids traversal ambiguities.
        filename = f"image-{digest}{suffix}"
        if digest not in packaged:
            content = source.read_bytes()
            if _sha256(content) != digest:
                raise RuntimeError("Una imagen materializada no coincide con su SHA-256.")
            _write_new(output_dir / filename, content)
            packaged[digest] = {
                "format": "image", "filename": filename,
                "bytes": len(content), "sha256": digest,
                "media_type": row.get("image_media_type"),
            }
        row["image_path"] = filename
    return list(packaged.values())


def _package_visual_assets(release: dict[str, Any], output_dir: Path, asset_root: Path | None) -> list[dict[str, Any]]:
    profile = release.get("definition", {}).get("visual_profile") or {}
    vehicle_sources = tuple(
        (f"vehicle-{str(source.get('vehicle_make_id') or '')[:8]}", source)
        for source in (profile.get("vehicle_makes") or {}).values()
    )
    sources = (("brand", profile), ("company", profile.get("company") or {})) + vehicle_sources
    entries: list[dict[str, Any]] = []
    if not any(source.get("logo_storage_relpath") or source.get("logo_relpath") for _, source in sources): return entries
    if asset_root is None: raise RuntimeError("El release contiene logos pero no se configuró brand_asset_root.")
    root = asset_root.resolve()
    for role, source in sources:
        relative = source.get("logo_storage_relpath") or source.get("logo_relpath")
        digest = str(source.get("logo_sha256") or "")
        if not relative: continue
        target = (root / str(relative)).resolve()
        if not target.is_relative_to(root) or not target.is_file() or _sha256(target.read_bytes()) != digest:
            raise RuntimeError(f"El logo {role} no supera la verificación SHA-256.")
        filename = f"{role}-logo{target.suffix.lower()}"; content = target.read_bytes()
        _write_new(output_dir / filename, content)
        source["packaged_logo_path"] = filename
        entries.append({"format": f"{role}-logo", "filename": filename, "bytes": len(content), "sha256": digest})
    return entries


def _release_metadata(release: dict[str, Any], item_count: int) -> dict[str, Any]:
    return {
        "release_id": str(release["catalog_release_id"]),
        "brand_id": str(release["brand_id"]),
        "version": str(release["version"]),
        "status": str(release["status"]),
        "snapshot_sha256": str(release["snapshot_sha256"]),
        "item_count": item_count,
        "visual_profile": dict((release.get("definition") or {}).get("visual_profile") or {}),
    }


def _indesign_rows(rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    """Expande multimarca para que cada separador InDesign reciba su ficha."""
    if "vehicle_make" not in {
        str(config.get("group_by") or ""), str(config.get("group_by_secondary") or "")
    }:
        return rows
    expanded: list[dict[str, Any]] = []
    for row in rows:
        makes = row.get("vehicle_makes") or ["Sin marca vehicular"]
        for make in makes:
            copy = dict(row)
            copy["vehicle_make"] = str(make)
            expanded.append(copy)
    return expanded


def _selection(rows: list[dict[str, Any]], config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    group_by = str(config.get("group_by") or "category_path")
    secondary = str(config.get("group_by_secondary") or "")
    filter_field = str(config.get("filter_field") or "all")
    query = str(config.get("filter_query") or "").strip()
    if group_by not in CATALOG_GROUP_FIELDS:
        raise ValueError("Agrupación principal no permitida.")
    if secondary and secondary not in CATALOG_GROUP_FIELDS:
        raise ValueError("Agrupación secundaria no permitida.")
    if secondary == group_by:
        secondary = ""
    if filter_field not in CATALOG_FILTER_FIELDS:
        raise ValueError("Campo de filtro no permitido.")
    if len(query) > 120:
        raise ValueError("El filtro no puede superar 120 caracteres.")
    raw_references = config.get("selected_references") or []
    if isinstance(raw_references, str):
        raw_references = re.split(r"[\r\n,;]+", raw_references)
    if not isinstance(raw_references, (list, tuple)):
        raise ValueError("La selección manual de referencias no es válida.")
    references: list[str] = []
    reference_keys: set[str] = set()
    for raw_reference in raw_references:
        reference = str(raw_reference).strip()
        if not reference:
            continue
        if len(reference) > 120:
            raise ValueError("Una referencia seleccionada supera 120 caracteres.")
        key = reference.casefold()
        if key not in reference_keys:
            reference_keys.add(key)
            references.append(reference)
    if len(references) > MAX_SELECTED_REFERENCES:
        raise ValueError(f"La selección manual supera {MAX_SELECTED_REFERENCES} referencias.")
    selected = rows
    if query:
        needle = query.casefold()
        keys = ("category_path", "brand", "vehicle_make", "internal_reference_original", "name_original") if filter_field == "all" else (filter_field,)
        selected = [row for row in rows if any(
            needle in (
                " ".join(map(str, row.get("vehicle_makes") or []))
                if key == "vehicle_make" else str(row.get(key) or "")
            ).casefold() for key in keys
        )]
    if reference_keys:
        available = {
            str(row.get("internal_reference_original") or "").strip().casefold()
            for row in rows
        }
        missing = [reference for reference in references if reference.casefold() not in available]
        if missing:
            sample = ", ".join(missing[:5])
            suffix = "…" if len(missing) > 5 else ""
            raise ValueError(f"Referencias no encontradas en el release: {sample}{suffix}")
        selected = [
            row for row in selected
            if str(row.get("internal_reference_original") or "").strip().casefold() in reference_keys
        ]
    if not selected:
        raise ValueError("El filtro no selecciona ningún producto.")
    config.update({
        "group_by": group_by, "group_by_secondary": secondary,
        "filter_field": filter_field, "filter_query": query,
        "selected_references": references,
    })
    return selected, {
        "source_item_count": len(rows), "selected_item_count": len(selected),
        "filter_field": filter_field, "filter_query": query,
        "group_by": group_by, "group_by_secondary": secondary or None,
        "selected_references": references,
        "selected_references_sha256": _sha256(_json_bytes(references)) if references else None,
    }


def build_catalog_bundle(
    release: dict[str, Any],
    items: Iterable[dict[str, Any]],
    output_dir: Path,
    *,
    formats: Iterable[str] = DEFAULT_FORMATS,
    config: dict[str, Any] | None = None,
    image_root: Path | None = None,
    brand_asset_root: Path | None = None,
    require_images: bool = False,
) -> dict[str, Any]:
    if release.get("status") != "published":
        raise PermissionError("Solo se puede exportar un release publicado.")
    requested = tuple(dict.fromkeys(formats))
    unsupported = sorted(set(requested) - set(SUPPORTED_FORMATS))
    if not requested or unsupported:
        raise ValueError(f"Formatos no soportados: {', '.join(unsupported) or 'ninguno'}.")

    materialized = list(items)
    source_rows = export_rows_from_release(release, materialized)
    if require_images and not any(row.get("image_storage_relpath") for row in source_rows):
        raise RuntimeError(
            "Este release fue construido sin imágenes aprobadas. Materializa las "
            "asociaciones y construye una versión nueva antes de exportar."
        )
    export_config = dict(config or {})
    template_profile = str(export_config.get("template_profile") or "T4").upper()
    if template_profile not in INDESIGN_TEMPLATE_PROFILES:
        raise ValueError("Perfil InDesign no soportado.")
    export_config["template_profile"] = template_profile
    theme = str(export_config.get("theme") or "forest").lower()
    if theme not in CATALOG_THEMES:
        raise ValueError("Tema editorial no soportado.")
    export_config["theme"] = theme
    rows, selection = _selection(source_rows, export_config)
    metadata = _release_metadata(release, len(source_rows))
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"El directorio de exportación no está vacío: {output_dir}")
    visual_files = _package_visual_assets(release, output_dir, brand_asset_root)
    # _package_visual_assets annotates the immutable in-memory definition copy with packaged paths.
    export_config["visual_profile"] = release.get("definition", {}).get("visual_profile") or {}
    image_files = _package_images(rows, output_dir, image_root)
    selected_image_count = sum(bool(row.get("image_path")) for row in rows)
    selection.update({
        "selected_image_count": selected_image_count,
        "missing_image_count": len(rows) - selected_image_count,
        "unique_image_file_count": len(image_files),
        "image_bytes": sum(int(item["bytes"]) for item in image_files),
    })
    stem = _safe_stem(f"catalogo-{release['version']}-{str(release['catalog_release_id'])[:8]}")
    payloads: dict[str, tuple[str, bytes]] = {}
    if "html" in requested:
        html_name = f"{stem}.html"
        html_content = generate_catalog_html(rows, export_config, release=metadata, bundle_dir=output_dir)
        payloads["html"] = (html_name, html_content)
        payloads["digital-zip"] = (
            f"{stem}.digital.zip", _digital_zip(html_content, image_files, output_dir)
        )
    if "html-standalone" in requested:
        payloads["html-standalone"] = (
            f"{stem}.autonomo.html",
            generate_catalog_html(
                rows, export_config, release=metadata,
                bundle_dir=output_dir, embed_images=True,
            ),
        )
    if "pdf" in requested:
        payloads["pdf"] = (
            f"{stem}.pdf", generate_catalog_pdf(rows, export_config, bundle_dir=output_dir, release=metadata)
        )
    if "pptx" in requested:
        payloads["pptx"] = (
            f"{stem}.pptx", generate_catalog_pptx(rows, export_config, bundle_dir=output_dir, release=metadata)
        )
    if "indesign-json" in requested:
        indesign_rows = _indesign_rows(rows, export_config)
        snapshot = {
            "schema": INDESIGN_SNAPSHOT_SCHEMA,
            "release": metadata,
            "layout": export_config,
            "products": indesign_rows,
        }
        snapshot_content = _json_bytes(snapshot)
        datamerge_content = generate_indesign_datamerge_csv(indesign_rows)
        payloads["indesign-json"] = (f"{stem}.indesign.json", snapshot_content)
        payloads["indesign-csv"] = (f"{stem}.datamerge.csv", datamerge_content)
        payloads["indesign-package"] = (
            f"{stem}.indesign.zip", _indesign_zip(
                snapshot_content, datamerge_content, visual_files + image_files, output_dir, export_config
            )
        )

    files: list[dict[str, Any]] = list(visual_files) + list(image_files)
    for export_format, (filename, content) in payloads.items():
        _write_new(output_dir / filename, content)
        files.append({
            "format": export_format,
            "filename": filename,
            "bytes": len(content),
            "sha256": _sha256(content),
        })
    manifest = {
        "schema": EXPORT_MANIFEST_SCHEMA,
        "release": metadata,
        "selection": selection,
        "layout": export_config,
        "files": files,
    }
    manifest_name = f"{stem}.manifest.json"
    _write_new(output_dir / manifest_name, _json_bytes(manifest))
    verification = verify_catalog_bundle(output_dir / manifest_name)
    return {
        **manifest, "output_dir": str(output_dir), "manifest": manifest_name,
        "verification": verification,
    }


def export_catalog_release(
    release_id: uuid.UUID,
    database: DatabaseConfig,
    password: str,
    output_dir: Path,
    *,
    formats: Iterable[str] = DEFAULT_FORMATS,
    config: dict[str, Any] | None = None,
    image_root: Path | None = None,
    brand_asset_root: Path | None = None,
    require_images: bool = False,
) -> dict[str, Any]:
    release, items = load_published_release(release_id, database, password)
    return build_catalog_bundle(
        release, items, output_dir, formats=formats, config=config, image_root=image_root,
        brand_asset_root=brand_asset_root,
        require_images=require_images,
    )


def create_operator_catalog_export(
    release_id: uuid.UUID,
    database: DatabaseConfig,
    password: str,
    output_root: Path,
    *,
    formats: Iterable[str],
    config: dict[str, Any],
    image_root: Path | None = None,
    brand_asset_root: Path | None = None,
) -> dict[str, Any]:
    export_id = uuid.uuid4()
    root = output_root.resolve()
    temporary = root / f".tmp-{export_id}"
    destination = root / str(release_id) / str(export_id)
    if destination.exists() or temporary.exists():
        raise FileExistsError("La identidad de exportación ya existe.")
    try:
        result = export_catalog_release(
            release_id, database, password, temporary,
            formats=formats, config=config, image_root=image_root,
            brand_asset_root=brand_asset_root, require_images=True,
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary.replace(destination)
    except Exception:
        if temporary.is_dir() and temporary.parent == root:
            shutil.rmtree(temporary)
        raise
    return {
        **result,
        "export_id": str(export_id),
        "output_dir": str(destination),
    }


def resolve_catalog_download(
    output_root: Path,
    release_id: uuid.UUID,
    export_id: uuid.UUID,
    filename: str,
) -> Path:
    if not filename or filename != Path(filename).name or len(filename) > 180:
        raise ValueError("Nombre de descarga inválido.")
    directory = output_root.resolve() / str(release_id) / str(export_id)
    manifests = list(directory.glob("*.manifest.json")) if directory.is_dir() else []
    if len(manifests) != 1:
        raise FileNotFoundError("La exportación no tiene un manifiesto único.")
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    if manifest.get("schema") != EXPORT_MANIFEST_SCHEMA:
        raise ValueError("El manifiesto de exportación no es compatible.")
    release = manifest.get("release") or {}
    if str(release.get("release_id")) != str(release_id):
        raise ValueError("El manifiesto no corresponde al release solicitado.")
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise ValueError("El manifiesto no enumera entregables.")
    if filename == manifests[0].name:
        verify_catalog_bundle(manifests[0])
        return manifests[0]
    matches = [item for item in entries if isinstance(item, dict) and item.get("filename") == filename]
    if len(matches) != 1:
        raise PermissionError("El archivo no pertenece al manifiesto de exportación.")
    entry = matches[0]
    target = (directory / filename).resolve()
    if not target.is_file() or target.parent.resolve() != directory.resolve():
        raise FileNotFoundError("El archivo exportado no existe.")
    expected_digest = str(entry.get("sha256") or "")
    if (
        not re.fullmatch(r"[0-9a-f]{64}", expected_digest)
        or target.stat().st_size != entry.get("bytes")
        or _sha256_file(target) != expected_digest
    ):
        raise ValueError("El archivo exportado no coincide con su manifiesto.")
    return target


def verify_catalog_bundle(manifest_path: Path) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    if not manifest_path.is_file() or not manifest_path.name.endswith(".manifest.json"):
        raise FileNotFoundError("No se encontró un manifiesto de exportación válido.")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("El manifiesto no es JSON UTF-8 válido.") from exc
    if manifest.get("schema") != EXPORT_MANIFEST_SCHEMA:
        raise ValueError("El esquema del manifiesto no es compatible.")
    release = manifest.get("release")
    files = manifest.get("files")
    if not isinstance(release, dict) or not re.fullmatch(r"[0-9a-f]{64}", str(release.get("snapshot_sha256") or "")):
        raise ValueError("El manifiesto no conserva un release verificable.")
    if not isinstance(files, list) or not files:
        raise ValueError("El manifiesto no enumera entregables.")
    directory = manifest_path.parent
    verified: dict[str, bytes] = {}
    formats: dict[str, str] = {}
    for entry in files:
        if not isinstance(entry, dict):
            raise ValueError("Una entrada del manifiesto no es válida.")
        filename = str(entry.get("filename") or "")
        digest = str(entry.get("sha256") or "")
        if filename != Path(filename).name or not filename or filename in verified:
            raise ValueError("El manifiesto contiene nombres duplicados o inseguros.")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"SHA-256 inválido para {filename}.")
        target = (directory / filename).resolve()
        if target.parent != directory or not target.is_file():
            raise FileNotFoundError(f"Falta el entregable {filename}.")
        content = target.read_bytes()
        if len(content) != entry.get("bytes") or _sha256(content) != digest:
            raise ValueError(f"El entregable {filename} no coincide con su manifiesto.")
        verified[filename] = content
        formats[str(entry.get("format") or "")] = filename
    expected_names = set(verified) | {manifest_path.name}
    actual_names = {path.name for path in directory.iterdir()}
    if actual_names != expected_names:
        unexpected = sorted(actual_names - expected_names)
        missing = sorted(expected_names - actual_names)
        raise ValueError(
            "El directorio no coincide exactamente con el manifiesto"
            f" (inesperados: {unexpected or 'ninguno'}; faltantes: {missing or 'ninguno'})."
        )
    image_names = {
        str(entry["filename"]): str(entry["sha256"])
        for entry in files if entry.get("format") == "image"
    }
    for package_format, required in (
        ("digital-zip", {"index.html"}),
        ("indesign-package", {"catalog.indesign.json", "catalog.datamerge.csv", "ImportPerfectCatalog.jsx", "LEEME-INDESIGN.txt"}),
    ):
        package_name = formats.get(package_format)
        if not package_name:
            continue
        try:
            with zipfile.ZipFile(io.BytesIO(verified[package_name])) as archive:
                infos = archive.infolist()
                names = [info.filename for info in infos]
                if len(names) != len(set(names)) or any(
                    not name or name.endswith("/") or Path(name).is_absolute()
                    or name.startswith(("/", "\\")) or ".." in Path(name).parts
                    or bool(info.flag_bits & 0x1)
                    for name, info in zip(names, infos, strict=True)
                ):
                    raise ValueError(f"El paquete {package_name} contiene rutas inseguras, cifradas o duplicadas.")
                image_bytes = sum(
                    int(entry["bytes"]) for entry in files if entry.get("format") == "image"
                )
                if sum(info.file_size for info in infos) > image_bytes + 512 * 1024 * 1024:
                    raise ValueError(f"El paquete {package_name} declara un tamaño descomprimido excesivo.")
                if not required.issubset(set(names)):
                    raise ValueError(f"El paquete {package_name} está incompleto.")
                for image_name, image_digest in image_names.items():
                    if image_name not in names or _sha256(archive.read(image_name)) != image_digest:
                        raise ValueError(f"El paquete {package_name} no conserva la imagen {image_name}.")
                if package_format == "indesign-package":
                    snapshot = json.loads(archive.read("catalog.indesign.json").decode("utf-8"))
                    if snapshot.get("schema") != INDESIGN_SNAPSHOT_SCHEMA or snapshot.get("release") != release:
                        raise ValueError("El paquete InDesign no corresponde al release del manifiesto.")
        except (zipfile.BadZipFile, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"El paquete {package_name} no es un ZIP verificable.") from exc
    return {
        "schema": EXPORT_VERIFICATION_SCHEMA,
        "release_id": str(release.get("release_id")),
        "snapshot_sha256": str(release["snapshot_sha256"]),
        "file_count": len(verified),
        "total_bytes": sum(len(content) for content in verified.values()),
        "status": "verified",
    }


def list_operator_catalog_exports(output_root: Path, *, limit: int = 100) -> list[dict[str, Any]]:
    if limit < 1 or limit > 500:
        raise ValueError("limit debe estar entre 1 y 500.")
    root = output_root.resolve()
    if not root.is_dir():
        return []
    results: list[dict[str, Any]] = []
    for manifest_path in sorted(root.glob("*/*/*.manifest.json"), reverse=True):
        try:
            release_id = uuid.UUID(manifest_path.parent.parent.name)
            export_id = uuid.UUID(manifest_path.parent.name)
            if manifest_path.resolve().parent.parent.parent != root:
                continue
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("schema") != EXPORT_MANIFEST_SCHEMA:
                continue
            files = list(manifest.get("files") or [])
            if any(not isinstance(item, dict) or "filename" not in item for item in files):
                continue
            results.append({
                "release_id": str(release_id),
                "export_id": str(export_id),
                "manifest": manifest_path.name,
                "release": manifest.get("release") or {},
                "selection": manifest.get("selection") or {
                    "selected_item_count": (manifest.get("release") or {}).get("item_count", 0),
                    "filter_query": "",
                },
                "layout": manifest.get("layout") or {},
                "files": files,
            })
        except (ValueError, OSError, json.JSONDecodeError):
            continue
        if len(results) >= limit:
            break
    return results


def build_catalog_preview(
    release: dict[str, Any], items: Iterable[dict[str, Any]],
    *, group_by: str = "category_path", group_by_secondary: str = "",
    filter_field: str = "all", filter_query: str = "",
    selected_references: str | list[str] | tuple[str, ...] = (), sample_limit: int = 24,
) -> dict[str, Any]:
    if sample_limit < 1 or sample_limit > 100:
        raise ValueError("sample_limit debe estar entre 1 y 100.")
    source_rows = export_rows_from_release(release, items)
    for index, row in enumerate(source_rows, start=1):
        row["preview_item"] = index
    preview_config = {
        "group_by": group_by, "group_by_secondary": group_by_secondary,
        "filter_field": filter_field, "filter_query": filter_query,
        "selected_references": selected_references,
    }
    rows, selection = _selection(source_rows, preview_config)
    groups: dict[str, dict[str, Any]] = {}
    sampled = 0
    for row in rows:
        primary_values = row.get("vehicle_makes") or ["Sin marca vehicular"] if group_by == "vehicle_make" else [row.get(group_by) or "Sin categoría"]
        secondary_field = preview_config["group_by_secondary"]
        secondary_values = row.get("vehicle_makes") or ["Sin marca vehicular"] if secondary_field == "vehicle_make" else [row.get(secondary_field) or "Sin subgrupo"] if secondary_field else [""]
        for primary in primary_values:
            for secondary in secondary_values:
                label = f"{primary} · {secondary}" if secondary else str(primary)
                group = groups.setdefault(label, {"label": label, "count": 0, "products": []})
                group["count"] += 1
                if sampled < sample_limit:
                    group["products"].append(row)
                    sampled += 1
    return {
        "release": _release_metadata(release, len(source_rows)),
        "group_by": group_by,
        "group_by_secondary": preview_config["group_by_secondary"],
        "filter_field": filter_field,
        "filter_query": filter_query,
        "selected_references": selection["selected_references"],
        "selected_references_sha256": selection["selected_references_sha256"],
        "source_count": selection["source_item_count"],
        "total_count": len(rows),
        "sample_count": sampled,
        "groups": list(groups.values()),
    }


def preview_catalog_release(
    release_id: uuid.UUID, database: DatabaseConfig, password: str,
    *, group_by: str = "category_path", group_by_secondary: str = "",
    filter_field: str = "all", filter_query: str = "", selected_references: str = "",
    sample_limit: int = 24,
) -> dict[str, Any]:
    release, items = load_published_release(release_id, database, password)
    return build_catalog_preview(
        release, items, group_by=group_by, group_by_secondary=group_by_secondary,
        filter_field=filter_field, filter_query=filter_query,
        selected_references=selected_references, sample_limit=sample_limit,
    )


def resolve_catalog_preview_image(
    release_id: uuid.UUID, item_number: int, database: DatabaseConfig, password: str,
    image_root: Path,
) -> Path:
    if item_number < 1:
        raise ValueError("item_number debe ser positivo.")
    release, items = load_published_release(release_id, database, password)
    rows = export_rows_from_release(release, items)
    if item_number > len(rows):
        raise FileNotFoundError("El producto no pertenece al release.")
    row = rows[item_number - 1]
    relative = row.get("image_storage_relpath")
    digest = str(row.get("image_sha256") or "")
    if not relative or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise FileNotFoundError("El producto no tiene una imagen aprobada.")
    root = image_root.resolve()
    target = (root / str(relative)).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise FileNotFoundError("La copia aprobada no está disponible.")
    if _sha256(target.read_bytes()) != digest:
        raise RuntimeError("La copia aprobada no coincide con el release.")
    return target
