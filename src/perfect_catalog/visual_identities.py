from __future__ import annotations

import hashlib
import re
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import psycopg
from PIL import Image as PILImage
from psycopg.rows import dict_row

from .brand_profiles import COLOR_PATTERN, _contrast_ratio
from .config import DatabaseConfig

MAX_LOGO_BYTES = 5 * 1024 * 1024
MEDIA = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml"}


def _validate_logo(filename: str, content: bytes) -> tuple[str, str]:
    suffix = Path(filename).suffix.lower()
    if suffix not in MEDIA or not content or len(content) > MAX_LOGO_BYTES:
        raise ValueError("El logo debe ser SVG, PNG o JPG y pesar como máximo 5 MiB.")
    if suffix == ".svg":
        try:
            root = ET.fromstring(content.decode("utf-8"))
        except (UnicodeDecodeError, ET.ParseError) as exc:
            raise ValueError("El SVG no es XML UTF-8 válido.") from exc
        serialized = content.lower()
        external_reference = any(
            value.strip().lower().startswith(("http://", "https://", "//", "javascript:"))
            for element in root.iter()
            for attribute, value in element.attrib.items()
            if attribute.rsplit("}", 1)[-1].lower() in {"href", "src"}
        )
        if any(token in serialized for token in (b"<script", b"foreignobject", b"javascript:")) or external_reference:
            raise ValueError("El SVG contiene scripts o recursos externos.")
        if not root.tag.endswith("svg"):
            raise ValueError("El archivo no contiene una raíz SVG.")
        extension = "svg"
    else:
        from io import BytesIO
        try:
            with PILImage.open(BytesIO(content)) as image:
                image.verify()
                if image.format not in {"PNG", "JPEG"}:
                    raise ValueError("El raster no es PNG o JPEG.")
        except Exception as exc:
            raise ValueError("El logo raster no es una imagen válida.") from exc
        extension = "png" if suffix == ".png" else "jpg"
    return MEDIA[suffix], extension


def list_visual_identities(
    config: DatabaseConfig, password: str, *, company_id: uuid.UUID,
) -> dict[str, Any]:
    with psycopg.connect(**config.connection_kwargs(password), row_factory=dict_row) as connection:
        rows = connection.execute(
            """SELECT DISTINCT ON (scope, company_id, brand_profile_id, vehicle_make_id) *
               FROM perfect_catalog.visual_identity_revision
               WHERE (scope='company' AND company_id=%s)
                  OR (scope='brand' AND EXISTS (
                        SELECT 1 FROM perfect_catalog.brand AS b
                        WHERE b.brand_profile_id=visual_identity_revision.brand_profile_id
                          AND b.company_id=%s
                     ))
                  OR scope='vehicle_make'
               ORDER BY scope, company_id, brand_profile_id, vehicle_make_id,
                        created_at DESC, visual_identity_revision_id DESC""",
            (company_id, company_id),
        ).fetchall()
        vehicle_makes = connection.execute(
            """SELECT vehicle_make_id, name, normalized_name
               FROM perfect_catalog.vehicle_make
               WHERE review_status='approved'
               ORDER BY name, vehicle_make_id"""
        ).fetchall()
    company = next((dict(row) for row in rows if row["scope"] == "company"), None)
    brands = {str(row["brand_profile_id"]): dict(row) for row in rows if row["scope"] == "brand"}
    vehicle_identities = {
        str(row["vehicle_make_id"]): dict(row) for row in rows if row["scope"] == "vehicle_make"
    }
    return {
        "company": company, "brands": brands,
        "vehicle_makes": [dict(row) for row in vehicle_makes],
        "vehicle_make_identities": vehicle_identities,
    }


def create_visual_identity(
    *, scope: str, company_id: uuid.UUID | None, brand_profile_id: uuid.UUID | None,
    vehicle_make_id: uuid.UUID | None = None, display_name: str,
    colors: dict[str, str], filename: str | None, content: bytes | None, actor: str, reason: str,
    asset_root: Path, config: DatabaseConfig, password: str,
) -> dict[str, Any]:
    targets = {
        "company": company_id is not None and brand_profile_id is None and vehicle_make_id is None,
        "brand": company_id is None and brand_profile_id is not None and vehicle_make_id is None,
        "vehicle_make": company_id is None and brand_profile_id is None and vehicle_make_id is not None,
    }
    if scope not in targets or not targets[scope]:
        raise ValueError("El alcance de identidad visual no es válido.")
    display_name, actor, reason = display_name.strip(), actor.strip(), reason.strip()
    if not display_name or len(display_name) > 120 or not actor or not 4 <= len(reason) <= 500:
        raise ValueError("Nombre, operador o motivo no son válidos.")
    normalized: dict[str, str] = {}
    for key in ("primary_color", "secondary_color", "ink_color", "paper_color"):
        value = str(colors.get(key) or "").upper()
        if not COLOR_PATTERN.fullmatch(value): raise ValueError("Los colores deben usar #RRGGBB.")
        normalized[key] = value
    if _contrast_ratio(normalized["ink_color"], normalized["paper_color"]) < 4.5 or _contrast_ratio(normalized["primary_color"], normalized["paper_color"]) < 4.5:
        raise ValueError("Texto y color principal deben alcanzar contraste 4.5:1 sobre el fondo.")
    with psycopg.connect(**config.connection_kwargs(password), row_factory=dict_row) as connection:
        if content:
            media_type, extension = _validate_logo(filename or "logo", content)
            digest = hashlib.sha256(content).hexdigest()
            relative = Path("objects") / digest[:2] / f"{digest}.{extension}"
            root = asset_root.resolve(); target = (root / relative).resolve()
            if not target.is_relative_to(root): raise ValueError("Ruta de logo no segura.")
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_bytes() != content: raise RuntimeError("Colisión SHA-256 de logo.")
            if not target.exists(): target.write_bytes(content)
            original_filename = Path(filename or "logo").name
        else:
            previous = connection.execute(
                """SELECT logo_sha256, logo_media_type, logo_storage_relpath, original_filename
                   FROM perfect_catalog.visual_identity_revision
                   WHERE scope=%s AND company_id IS NOT DISTINCT FROM %s
                     AND brand_profile_id IS NOT DISTINCT FROM %s
                     AND vehicle_make_id IS NOT DISTINCT FROM %s
                   ORDER BY created_at DESC, visual_identity_revision_id DESC LIMIT 1""",
                (scope, company_id, brand_profile_id, vehicle_make_id),
            ).fetchone()
            if previous is None:
                raise ValueError("Debes seleccionar un logo para crear esta identidad.")
            digest = previous["logo_sha256"]
            media_type = previous["logo_media_type"]
            relative = Path(previous["logo_storage_relpath"])
            original_filename = previous["original_filename"]
        row = connection.execute(
            """INSERT INTO perfect_catalog.visual_identity_revision (
                 visual_identity_revision_id, scope, company_id, brand_profile_id, vehicle_make_id, display_name,
                 primary_color, secondary_color, ink_color, paper_color, logo_sha256,
                 logo_media_type, logo_storage_relpath, original_filename, created_by, creation_reason
               ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (uuid.uuid4(), scope, company_id, brand_profile_id, vehicle_make_id, display_name, normalized["primary_color"],
             normalized["secondary_color"], normalized["ink_color"], normalized["paper_color"],
             digest, media_type, relative.as_posix(), original_filename, actor, reason),
        ).fetchone()
    return dict(row)


def resolve_visual_identity_asset(
    revision_id: uuid.UUID, asset_root: Path, config: DatabaseConfig, password: str,
) -> tuple[Path, str]:
    with psycopg.connect(**config.connection_kwargs(password), row_factory=dict_row) as connection:
        row = connection.execute(
            "SELECT logo_storage_relpath, logo_sha256, logo_media_type FROM perfect_catalog.visual_identity_revision WHERE visual_identity_revision_id=%s",
            (revision_id,),
        ).fetchone()
    if row is None: raise FileNotFoundError("No existe la revisión visual.")
    root = asset_root.resolve(); target = (root / row["logo_storage_relpath"]).resolve()
    if not target.is_relative_to(root) or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != row["logo_sha256"]:
        raise FileNotFoundError("El logo no supera su verificación.")
    return target, str(row["logo_media_type"])
