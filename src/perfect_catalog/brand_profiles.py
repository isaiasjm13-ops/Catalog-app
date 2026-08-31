from __future__ import annotations

import re
import uuid
from typing import Any
from urllib.parse import urlsplit

import psycopg
from psycopg.rows import dict_row

from .config import DatabaseConfig


PROFILE_NAMESPACE = uuid.UUID("4c5ddbcf-f5c3-49e8-aee1-a78a47d6d293")
CODE_PATTERN = re.compile(r"[A-Z0-9][A-Z0-9_-]{1,31}")
COLOR_PATTERN = re.compile(r"#[0-9A-F]{6}")


def _contrast_ratio(first: str, second: str) -> float:
    def luminance(color: str) -> float:
        channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4 for value in channels]
        return .2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2]
    lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (lighter + .05) / (darker + .05)


def visual_profile(row: dict[str, Any]) -> dict[str, Any]:
    """Serializable, immutable subset used by release/export snapshots."""
    return {
        key: row.get(key) for key in (
            "code", "display_name", "tagline", "primary_color", "secondary_color",
            "ink_color", "paper_color", "public_base_url", "title_font_family",
            "body_font_family", "minimum_font_size_pt", "body_line_height",
            "logo_asset_key", "corner_logo_enabled", "watermark_enabled",
            "watermark_opacity",
        )
    }


def normalize_profile_input(values: dict[str, str]) -> dict[str, str | None]:
    code = str(values.get("code") or "").strip().upper()
    if not CODE_PATTERN.fullmatch(code):
        raise ValueError("El codigo debe usar 2-32 letras, numeros, guion o guion bajo.")
    name = str(values.get("display_name") or "").strip()
    if not 1 <= len(name) <= 120:
        raise ValueError("El nombre debe contener entre 1 y 120 caracteres.")
    tagline = str(values.get("tagline") or "").strip() or None
    if tagline and len(tagline) > 180:
        raise ValueError("El eslogan no puede superar 180 caracteres.")
    colors: dict[str, str] = {}
    for field in ("primary_color", "secondary_color", "ink_color", "paper_color"):
        color = str(values.get(field) or "").strip().upper()
        if not COLOR_PATTERN.fullmatch(color):
            raise ValueError(f"{field} debe tener formato hexadecimal #RRGGBB.")
        colors[field] = color
    if _contrast_ratio(colors["ink_color"], colors["paper_color"]) < 4.5:
        raise ValueError("Texto y fondo deben alcanzar contraste WCAG AA de 4.5:1.")
    if _contrast_ratio(colors["primary_color"], colors["paper_color"]) < 4.5:
        raise ValueError("El color primario sobre el fondo debe alcanzar contraste WCAG AA de 4.5:1.")
    public_url = str(values.get("public_base_url") or "").strip() or None
    if public_url:
        parsed = urlsplit(public_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("La URL publica debe ser HTTPS y no incluir credenciales.")
        if len(public_url) > 500:
            raise ValueError("La URL publica no puede superar 500 caracteres.")
    return {"code": code, "display_name": name, "tagline": tagline, **colors, "public_base_url": public_url}


def list_brand_profiles(
    config: DatabaseConfig, password: str, *, company_id: uuid.UUID,
) -> list[dict[str, Any]]:
    with psycopg.connect(**config.connection_kwargs(password), row_factory=dict_row) as connection:
        rows = connection.execute(
            "SELECT * FROM perfect_catalog.brand_profile WHERE company_id=%s ORDER BY display_name, code",
            (company_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def create_brand_profile(
    values: dict[str, str], actor: str, reason: str, company_id: uuid.UUID,
    config: DatabaseConfig, password: str,
) -> dict[str, Any]:
    profile = normalize_profile_input(values)
    actor = str(actor or "").strip()
    reason = str(reason or "").strip()
    if not actor or len(actor) > 120:
        raise ValueError("El operador de la marca no es valido.")
    if not 4 <= len(reason) <= 500:
        raise ValueError("El motivo debe contener entre 4 y 500 caracteres.")
    profile_id = uuid.uuid5(PROFILE_NAMESPACE, str(profile["code"]))
    with psycopg.connect(**config.connection_kwargs(password), row_factory=dict_row) as connection:
        existing = connection.execute(
            "SELECT * FROM perfect_catalog.brand_profile WHERE code=%s", (profile["code"],)
        ).fetchone()
        if existing is not None:
            raise ValueError("Ya existe un perfil con ese codigo.")
        row = connection.execute(
            """
            INSERT INTO perfect_catalog.brand_profile (
                brand_profile_id, company_id, code, display_name, tagline, primary_color,
                secondary_color, ink_color, paper_color, public_base_url,
                created_by, creation_reason
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING *
            """,
            (profile_id, company_id, profile["code"], profile["display_name"], profile["tagline"],
             profile["primary_color"], profile["secondary_color"], profile["ink_color"],
             profile["paper_color"], profile["public_base_url"], actor, reason),
        ).fetchone()
    return dict(row)
