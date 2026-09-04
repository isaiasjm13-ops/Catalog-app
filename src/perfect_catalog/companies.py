from __future__ import annotations

import re
import unicodedata
import uuid
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .config import DatabaseConfig

CODE_PATTERN = re.compile(r"[A-Z0-9][A-Z0-9_-]{1,31}")


def _normalized(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value)
    return " ".join("".join(ch for ch in plain if not unicodedata.combining(ch)).upper().split())


def create_company(*, code: str, display_name: str, actor: str, reason: str,
                   config: DatabaseConfig, password: str) -> dict[str, Any]:
    code = str(code or "").strip().upper()
    display_name, actor, reason = (str(value or "").strip() for value in (display_name, actor, reason))
    if not CODE_PATTERN.fullmatch(code):
        raise ValueError("El código debe usar 2-32 letras, números, guion o guion bajo.")
    if not 1 <= len(display_name) <= 120 or not actor or not 4 <= len(reason) <= 500:
        raise ValueError("Nombre, operador o motivo no son válidos.")
    company_id = uuid.uuid4()
    with psycopg.connect(**config.connection_kwargs(password), row_factory=dict_row) as connection:
        row = connection.execute(
            """INSERT INTO perfect_catalog.company
                   (company_id, code, display_name, normalized_name)
               VALUES (%s,%s,%s,%s) RETURNING *""",
            (company_id, code, display_name, _normalized(display_name)),
        ).fetchone()
        connection.execute(
            """INSERT INTO perfect_catalog.company_admin_event
                   (company_admin_event_id, company_id, action, code_snapshot,
                    display_name_snapshot, actor, reason)
               VALUES (%s,%s,'created',%s,%s,%s,%s)""",
            (uuid.uuid4(), company_id, code, display_name, actor, reason),
        )
    return dict(row)


def set_company_active(*, company_id: uuid.UUID, active: bool, actor: str, reason: str,
                       config: DatabaseConfig, password: str) -> dict[str, Any]:
    actor, reason = str(actor or "").strip(), str(reason or "").strip()
    if not actor or not 4 <= len(reason) <= 500:
        raise ValueError("Operador o motivo no son válidos.")
    with psycopg.connect(**config.connection_kwargs(password), row_factory=dict_row) as connection:
        connection.execute("SELECT pg_advisory_xact_lock(hashtext('perfect_catalog.company_admin'))")
        row = connection.execute(
            "SELECT * FROM perfect_catalog.company WHERE company_id=%s", (company_id,),
        ).fetchone()
        if row is None:
            raise ValueError("La empresa no existe.")
        if bool(row["is_active"]) == active:
            raise ValueError("La empresa ya tiene ese estado.")
        if not active:
            active_count = connection.execute(
                "SELECT count(*) FROM perfect_catalog.company WHERE is_active=true"
            ).fetchone()[0]
            if active_count <= 1:
                raise ValueError("No puedes desactivar la última empresa activa.")
        updated = connection.execute(
            """UPDATE perfect_catalog.company SET is_active=%s, updated_at=CURRENT_TIMESTAMP
               WHERE company_id=%s RETURNING *""", (active, company_id),
        ).fetchone()
        connection.execute(
            """INSERT INTO perfect_catalog.company_admin_event
                   (company_admin_event_id, company_id, action, code_snapshot,
                    display_name_snapshot, actor, reason)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (uuid.uuid4(), company_id, "reactivated" if active else "deactivated",
             row["code"], row["display_name"], actor, reason),
        )
    return dict(updated)
