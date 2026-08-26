from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any, Iterable

from .catalog_exports import export_rows_from_release, generate_catalog_pdf, generate_catalog_pptx
from .config import DatabaseConfig
from .publication import load_published_release

INDESIGN_SNAPSHOT_SCHEMA = "perfect-catalog.indesign-snapshot.v1"
EXPORT_MANIFEST_SCHEMA = "perfect-catalog.export-manifest.v1"
SUPPORTED_FORMATS = ("pdf", "pptx", "indesign-json")
INDESIGN_TEMPLATE_PROFILES = ("T4", "T2", "T1", "TABLE")
CATALOG_GROUP_FIELDS = ("category_path", "brand", "internal_reference_original")
CATALOG_FILTER_FIELDS = ("all", "category_path", "brand", "internal_reference_original", "name_original")


def _safe_stem(value: object) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value)).strip("-._")
    return stem[:80] or "catalog"


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


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


def _release_metadata(release: dict[str, Any], item_count: int) -> dict[str, Any]:
    return {
        "release_id": str(release["catalog_release_id"]),
        "brand_id": str(release["brand_id"]),
        "version": str(release["version"]),
        "status": str(release["status"]),
        "snapshot_sha256": str(release["snapshot_sha256"]),
        "item_count": item_count,
    }


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
    selected = rows
    if query:
        needle = query.casefold()
        keys = ("category_path", "brand", "internal_reference_original", "name_original") if filter_field == "all" else (filter_field,)
        selected = [row for row in rows if any(needle in str(row.get(key) or "").casefold() for key in keys)]
    if not selected:
        raise ValueError("El filtro no selecciona ningún producto.")
    config.update({"group_by": group_by, "group_by_secondary": secondary, "filter_field": filter_field, "filter_query": query})
    return selected, {
        "source_item_count": len(rows), "selected_item_count": len(selected),
        "filter_field": filter_field, "filter_query": query,
        "group_by": group_by, "group_by_secondary": secondary or None,
    }


def build_catalog_bundle(
    release: dict[str, Any],
    items: Iterable[dict[str, Any]],
    output_dir: Path,
    *,
    formats: Iterable[str] = SUPPORTED_FORMATS,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if release.get("status") != "published":
        raise PermissionError("Solo se puede exportar un release publicado.")
    requested = tuple(dict.fromkeys(formats))
    unsupported = sorted(set(requested) - set(SUPPORTED_FORMATS))
    if not requested or unsupported:
        raise ValueError(f"Formatos no soportados: {', '.join(unsupported) or 'ninguno'}.")

    materialized = list(items)
    source_rows = export_rows_from_release(release, materialized)
    export_config = dict(config or {})
    template_profile = str(export_config.get("template_profile") or "T4").upper()
    if template_profile not in INDESIGN_TEMPLATE_PROFILES:
        raise ValueError("Perfil InDesign no soportado.")
    export_config["template_profile"] = template_profile
    rows, selection = _selection(source_rows, export_config)
    metadata = _release_metadata(release, len(source_rows))
    stem = _safe_stem(f"catalogo-{release['version']}-{str(release['catalog_release_id'])[:8]}")
    payloads: dict[str, tuple[str, bytes]] = {}
    if "pdf" in requested:
        payloads["pdf"] = (f"{stem}.pdf", generate_catalog_pdf(rows, export_config))
    if "pptx" in requested:
        payloads["pptx"] = (f"{stem}.pptx", generate_catalog_pptx(rows, export_config))
    if "indesign-json" in requested:
        snapshot = {
            "schema": INDESIGN_SNAPSHOT_SCHEMA,
            "release": metadata,
            "layout": export_config,
            "products": rows,
        }
        payloads["indesign-json"] = (f"{stem}.indesign.json", _json_bytes(snapshot))

    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"El directorio de exportación no está vacío: {output_dir}")
    files: list[dict[str, Any]] = []
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
        "files": files,
    }
    manifest_name = f"{stem}.manifest.json"
    _write_new(output_dir / manifest_name, _json_bytes(manifest))
    return {**manifest, "output_dir": str(output_dir), "manifest": manifest_name}


def export_catalog_release(
    release_id: uuid.UUID,
    database: DatabaseConfig,
    password: str,
    output_dir: Path,
    *,
    formats: Iterable[str] = SUPPORTED_FORMATS,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    release, items = load_published_release(release_id, database, password)
    return build_catalog_bundle(release, items, output_dir, formats=formats, config=config)


def create_operator_catalog_export(
    release_id: uuid.UUID,
    database: DatabaseConfig,
    password: str,
    output_root: Path,
    *,
    formats: Iterable[str],
    config: dict[str, Any],
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
            formats=formats, config=config,
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
    allowed = {manifests[0].name}
    allowed.update(str(item["filename"]) for item in manifest.get("files", []))
    if filename not in allowed:
        raise PermissionError("El archivo no pertenece al manifiesto de exportación.")
    target = directory / filename
    if not target.is_file() or target.parent.resolve() != directory.resolve():
        raise FileNotFoundError("El archivo exportado no existe.")
    return target


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
    filter_field: str = "all", filter_query: str = "", sample_limit: int = 24,
) -> dict[str, Any]:
    if sample_limit < 1 or sample_limit > 100:
        raise ValueError("sample_limit debe estar entre 1 y 100.")
    source_rows = export_rows_from_release(release, items)
    preview_config = {
        "group_by": group_by, "group_by_secondary": group_by_secondary,
        "filter_field": filter_field, "filter_query": filter_query,
    }
    rows, selection = _selection(source_rows, preview_config)
    groups: dict[str, dict[str, Any]] = {}
    sampled = 0
    for row in rows:
        primary = str(row.get(group_by) or "Sin categoría")
        secondary = str(row.get(preview_config["group_by_secondary"]) or "Sin subgrupo") if preview_config["group_by_secondary"] else ""
        label = f"{primary} · {secondary}" if secondary else primary
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
        "source_count": selection["source_item_count"],
        "total_count": len(rows),
        "sample_count": sampled,
        "groups": list(groups.values()),
    }


def preview_catalog_release(
    release_id: uuid.UUID, database: DatabaseConfig, password: str,
    *, group_by: str = "category_path", group_by_secondary: str = "",
    filter_field: str = "all", filter_query: str = "", sample_limit: int = 24,
) -> dict[str, Any]:
    release, items = load_published_release(release_id, database, password)
    return build_catalog_preview(
        release, items, group_by=group_by, group_by_secondary=group_by_secondary,
        filter_field=filter_field, filter_query=filter_query, sample_limit=sample_limit,
    )
