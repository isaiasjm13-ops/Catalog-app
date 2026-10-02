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


def list_profiles_without_brand(
    config: DatabaseConfig, password: str, *, company_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Perfiles visuales de la Company que todavia no tienen una Brand real con su mismo codigo.
    Un perfil solo no basta para importar: el dry-run exige la Brand."""
    with psycopg.connect(**config.connection_kwargs(password), row_factory=dict_row) as connection:
        rows = connection.execute(
            """
            SELECT bp.brand_profile_id, bp.code, bp.display_name
            FROM perfect_catalog.brand_profile AS bp
            WHERE bp.company_id = %s
              AND NOT EXISTS (SELECT 1 FROM perfect_catalog.brand AS b WHERE b.code = bp.code)
            ORDER BY bp.display_name, bp.code
            """,
            (company_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def create_brand_for_profile(
    *, brand_profile_id: uuid.UUID, actor: str, company_id: uuid.UUID,
    config: DatabaseConfig, password: str,
) -> dict[str, Any]:
    """Crea la Brand real de un perfil existente, igual a como la crearia el importador al aplicar
    un plan (mismo id, nombre normalizado y fuente), para que el dry-run deje de fallar con
    'La Brand no existe'. Respeta la politica Company/Brand y deja un evento de vinculo auditado."""
    from .canonical import normalize_name
    from .import_context import is_company_brand_allowed
    from .importer import NAMESPACE, SOURCE_CODE, SOURCE_MODEL
    from psycopg.types.json import Jsonb

    actor = str(actor or "").strip()
    if not actor or len(actor) > 120:
        raise ValueError("El operador no es valido.")
    with psycopg.connect(**config.connection_kwargs(password), row_factory=dict_row) as connection:
        connection.execute("SELECT pg_advisory_xact_lock(hashtext('perfect_catalog.brand_profile_link'))")
        profile = connection.execute(
            """SELECT bp.brand_profile_id, bp.code, bp.display_name, bp.company_id, c.code AS company_code
               FROM perfect_catalog.brand_profile AS bp
               JOIN perfect_catalog.company AS c ON c.company_id = bp.company_id
               WHERE bp.brand_profile_id=%s""",
            (brand_profile_id,),
        ).fetchone()
        if profile is None or profile["company_id"] != company_id:
            raise ValueError("El perfil de marca no existe en la Company activa.")
        if not is_company_brand_allowed(profile["company_code"], profile["code"]):
            raise ValueError(
                f"La marca {profile['code']} no esta autorizada para la Company {profile['company_code']}. "
                "Las marcas permitidas por Company se definen en import_context.is_company_brand_allowed."
            )
        existing = connection.execute(
            "SELECT brand_id, company_id, brand_profile_id FROM perfect_catalog.brand WHERE code=%s",
            (profile["code"],),
        ).fetchone()
        if existing is not None:
            raise ValueError(
                f"Ya existe una marca con el codigo {profile['code']}; "
                "vinculala a su perfil desde 'Vincular marca con su perfil visual'."
            )
        normalized = normalize_name(profile["display_name"])
        brand_id = uuid.uuid5(NAMESPACE, f"brand:{normalized}")
        by_name = connection.execute(
            "SELECT code FROM perfect_catalog.brand WHERE brand_id=%s", (brand_id,),
        ).fetchone()
        if by_name is not None:
            raise ValueError(
                f"Ya existe una marca con el nombre {profile['display_name']!r} bajo el codigo {by_name['code']}."
            )
        source_system_id = uuid.uuid5(NAMESPACE, "source-system:odoo")  # igual que importer.py
        source_row = connection.execute(
            """
            INSERT INTO perfect_catalog.source_system (
                source_system_id, code, name, system_type, timezone_name, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (code) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
            RETURNING source_system_id
            """,
            (source_system_id, SOURCE_CODE, "Odoo", "erp", "America/Panama",
             Jsonb({"source_model": SOURCE_MODEL})),
        ).fetchone()
        connection.execute(
            """
            INSERT INTO perfect_catalog.brand (
                brand_id, source_system_id, brand_profile_id, company_id, code, name, normalized_name
            ) VALUES (%s,%s,%s,%s,%s,%s,%s)
            """,
            (brand_id, source_row["source_system_id"], brand_profile_id, company_id,
             profile["code"], profile["display_name"], normalized),
        )
        connection.execute(
            """
            INSERT INTO perfect_catalog.brand_profile_link_event (
                brand_profile_link_event_id, brand_id, previous_brand_profile_id,
                new_brand_profile_id, actor, reason
            ) VALUES (%s,%s,NULL,%s,%s,%s)
            """,
            (uuid.uuid4(), brand_id, brand_profile_id, actor,
             f"Alta de la marca real {profile['code']} desde su perfil visual"),
        )
    return {"status": "created", "brand_id": str(brand_id), "code": profile["code"]}


def list_company_brands(
    config: DatabaseConfig, password: str, *, company_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Brands reales (perfect_catalog.brand) de la Company, con su vinculo de perfil si existe.

    Distinto de list_brand_profiles: un brand_profile puede existir sin que ninguna Brand
    lo tenga asignado todavia, y una Brand puede existir (sembrada por migracion o creada
    por un alta previa) sin perfil. El dry-run exige el vinculo; esta lista es la evidencia
    que el operador necesita para completarlo desde /operator/brands.
    """
    with psycopg.connect(**config.connection_kwargs(password), row_factory=dict_row) as connection:
        rows = connection.execute(
            """
            SELECT b.brand_id, b.code, b.name, b.is_active, b.brand_profile_id,
                   bp.code AS linked_profile_code, bp.display_name AS linked_profile_name
            FROM perfect_catalog.brand AS b
            LEFT JOIN perfect_catalog.brand_profile AS bp
              ON bp.brand_profile_id = b.brand_profile_id
            WHERE b.company_id = %s
            ORDER BY b.name, b.code
            """,
            (company_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def link_brand_profile(
    *, brand_id: uuid.UUID, brand_profile_id: uuid.UUID,
    expected_previous_brand_profile_id: uuid.UUID | None,
    actor: str, reason: str, config: DatabaseConfig, password: str,
) -> dict[str, Any]:
    actor = str(actor or "").strip()
    reason = str(reason or "").strip()
    if not actor or len(actor) > 120:
        raise ValueError("El operador no es valido.")
    if not 4 <= len(reason) <= 500:
        raise ValueError("El motivo debe contener entre 4 y 500 caracteres.")
    with psycopg.connect(**config.connection_kwargs(password), row_factory=dict_row) as connection:
        connection.execute("SELECT pg_advisory_xact_lock(hashtext('perfect_catalog.brand_profile_link'))")
        brand = connection.execute(
            """SELECT brand_id, company_id, brand_profile_id, is_active
               FROM perfect_catalog.brand WHERE brand_id=%s FOR UPDATE""",
            (brand_id,),
        ).fetchone()
        if brand is None or not brand["is_active"]:
            raise ValueError("La marca no existe o esta inactiva.")
        if brand["brand_profile_id"] != expected_previous_brand_profile_id:
            raise PermissionError(
                "El vinculo actual de la marca cambio desde que abriste esta pagina; recarga e intenta de nuevo."
            )
        profile = connection.execute(
            "SELECT brand_profile_id, company_id FROM perfect_catalog.brand_profile WHERE brand_profile_id=%s",
            (brand_profile_id,),
        ).fetchone()
        if profile is None:
            raise ValueError("El perfil de marca no existe.")
        if profile["company_id"] != brand["company_id"]:
            raise ValueError("El perfil de marca pertenece a otra Company.")
        if brand["brand_profile_id"] == brand_profile_id:
            raise ValueError("La marca ya esta vinculada a ese perfil.")
        updated = connection.execute(
            """UPDATE perfect_catalog.brand SET brand_profile_id=%s, updated_at=CURRENT_TIMESTAMP
               WHERE brand_id=%s RETURNING *""",
            (brand_profile_id, brand_id),
        ).fetchone()
        connection.execute(
            """
            INSERT INTO perfect_catalog.brand_profile_link_event (
                brand_profile_link_event_id, brand_id, previous_brand_profile_id,
                new_brand_profile_id, actor, reason
            ) VALUES (%s,%s,%s,%s,%s,%s)
            """,
            (uuid.uuid4(), brand_id, brand["brand_profile_id"], brand_profile_id, actor, reason),
        )
    return dict(updated)
