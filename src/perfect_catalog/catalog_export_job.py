from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Iterable

from .catalog_exports import export_rows_from_release, generate_catalog_pdf, generate_catalog_pptx
from .config import DatabaseConfig
from .publication import load_published_release

INDESIGN_SNAPSHOT_SCHEMA = "perfect-catalog.indesign-snapshot.v1"
EXPORT_MANIFEST_SCHEMA = "perfect-catalog.export-manifest.v1"
SUPPORTED_FORMATS = ("pdf", "pptx", "indesign-json")


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
    rows = export_rows_from_release(release, materialized)
    export_config = dict(config or {})
    metadata = _release_metadata(release, len(rows))
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
