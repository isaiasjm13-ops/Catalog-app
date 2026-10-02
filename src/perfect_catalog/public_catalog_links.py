"""Links de acceso y bitácora de auditoría del generador público de catálogos.

Dos tablas, sin relación (sin FK) con `product_reference`/`company`/`brand`: son
solo control de acceso y bitácora, nunca catálogo real, así que nada de lo que
pase aquí puede chocar con datos de producto existentes."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .config import DatabaseConfig


def _require_text(value: str, label: str, *, max_length: int = 200) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} no puede estar vacío.")
    if len(text) > max_length:
        raise ValueError(f"{label} no puede superar {max_length} caracteres.")
    return text


def create_public_catalog_link(
    config: DatabaseConfig, password: str, *, label: str, actor: str,
) -> dict[str, Any]:
    label = _require_text(label, "label", max_length=120)
    actor = _require_text(actor, "actor")
    link_id = uuid.uuid4()
    token = secrets.token_urlsafe(24)
    now = datetime.now(UTC)
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        connection.execute(
            """
            INSERT INTO perfect_catalog.public_catalog_link (
                public_catalog_link_id, token, label, created_by_actor, created_at
            ) VALUES (%s, %s, %s, %s, %s)
            """,
            (link_id, token, label, actor, now),
        )
    return {"public_catalog_link_id": str(link_id), "token": token, "label": label}


def list_public_catalog_links(config: DatabaseConfig, password: str) -> list[dict[str, Any]]:
    with psycopg.connect(**config.connection_kwargs(password), row_factory=dict_row) as connection:
        rows = connection.execute(
            """
            SELECT l.public_catalog_link_id, l.token, l.label, l.created_by_actor, l.created_at,
                   r.created_at AS revoked_at, (r.created_at IS NULL) AS active,
                   count(g.public_catalog_generation_id) AS generation_count
            FROM perfect_catalog.public_catalog_link AS l
            LEFT JOIN perfect_catalog.public_catalog_link_revocation_event AS r
              ON r.public_catalog_link_id = l.public_catalog_link_id
            LEFT JOIN perfect_catalog.public_catalog_generation AS g
              ON g.public_catalog_link_id = l.public_catalog_link_id
            GROUP BY l.public_catalog_link_id, l.token, l.label, l.created_by_actor,
                     l.created_at, r.created_at
            ORDER BY l.created_at DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def revoke_public_catalog_link(
    config: DatabaseConfig, password: str, *, link_id: uuid.UUID, actor: str,
) -> dict[str, Any]:
    actor = _require_text(actor, "actor")
    event_id = uuid.uuid4()
    with psycopg.connect(**config.connection_kwargs(password), row_factory=dict_row) as connection:
        link = connection.execute(
            "SELECT public_catalog_link_id, label FROM perfect_catalog.public_catalog_link WHERE public_catalog_link_id = %s",
            (link_id,),
        ).fetchone()
        if link is None:
            raise ValueError("El link no existe.")
        already_revoked = connection.execute(
            "SELECT 1 FROM perfect_catalog.public_catalog_link_revocation_event WHERE public_catalog_link_id = %s",
            (link_id,),
        ).fetchone()
        if already_revoked is not None:
            raise ValueError("El link ya estaba revocado.")
        connection.execute(
            """
            INSERT INTO perfect_catalog.public_catalog_link_revocation_event (
                public_catalog_link_revocation_event_id, public_catalog_link_id, actor
            ) VALUES (%s, %s, %s)
            """,
            (event_id, link_id, actor),
        )
    return dict(link)


def resolve_public_catalog_link(
    config: DatabaseConfig, password: str, *, token: str,
) -> dict[str, Any] | None:
    token = str(token or "").strip()
    if not token:
        return None
    with psycopg.connect(**config.connection_kwargs(password), row_factory=dict_row) as connection:
        row = connection.execute(
            """
            SELECT l.public_catalog_link_id, l.label
            FROM perfect_catalog.public_catalog_link AS l
            WHERE l.token = %s
              AND NOT EXISTS (
                  SELECT 1 FROM perfect_catalog.public_catalog_link_revocation_event AS r
                  WHERE r.public_catalog_link_id = l.public_catalog_link_id
              )
            """,
            (token,),
        ).fetchone()
    return dict(row) if row is not None else None


def record_public_catalog_generation(
    config: DatabaseConfig, password: str, *, link_id: uuid.UUID, declared_name: str,
    product_count: int, matched_image_count: int, unmatched_image_count: int,
    ambiguous_image_count: int, excel_sha256: str, client_ip: str | None,
) -> dict[str, Any]:
    declared_name = _require_text(declared_name, "declared_name", max_length=200)
    generation_id = uuid.uuid4()
    now = datetime.now(UTC)
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        connection.execute(
            """
            INSERT INTO perfect_catalog.public_catalog_generation (
                public_catalog_generation_id, public_catalog_link_id, declared_name,
                product_count, matched_image_count, unmatched_image_count,
                ambiguous_image_count, excel_sha256, client_ip, generated_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (generation_id, link_id, declared_name, product_count, matched_image_count,
             unmatched_image_count, ambiguous_image_count, excel_sha256, client_ip, now),
        )
    return {"public_catalog_generation_id": str(generation_id)}


def list_public_catalog_generations(
    config: DatabaseConfig, password: str, *, link_id: uuid.UUID,
    limit: int = 50, offset: int = 0,
) -> list[dict[str, Any]]:
    with psycopg.connect(**config.connection_kwargs(password), row_factory=dict_row) as connection:
        rows = connection.execute(
            """
            SELECT public_catalog_generation_id, declared_name, product_count,
                   matched_image_count, unmatched_image_count, ambiguous_image_count,
                   excel_sha256, client_ip, generated_at
            FROM perfect_catalog.public_catalog_generation
            WHERE public_catalog_link_id = %s
            ORDER BY generated_at DESC
            LIMIT %s OFFSET %s
            """,
            (link_id, limit, offset),
        ).fetchall()
    return [dict(row) for row in rows]
