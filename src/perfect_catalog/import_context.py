from __future__ import annotations

import uuid
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row


# Companies que no importan productos propios (sus marcas viven en otra Company).
COMPANIES_WITHOUT_IMPORTS = {'MASAKI'}


def is_company_brand_allowed(company_code: str, brand_code: str) -> bool:
    """Una marca nueva de una Company no necesita tocar el código: la pertenencia Brand -> Company
    ya es autoritativa (resolve_import_context exige que la Brand sea de la Company activa, así
    que PERFECT nunca importa una marca de NATSUKI aunque aquí se permita cualquier código).
    Antes había listas fijas por Company (PERFECT: 3 marcas, KMC: A1, NATSUKI: NATSUKI) que
    obligaban a editar el programa por cada marca nueva."""
    company = str(company_code or '').strip().upper()
    brand = str(brand_code or '').strip().upper()
    if not brand or company in COMPANIES_WITHOUT_IMPORTS:
        return False
    return True


def resolve_import_context(
    connection: Connection[Any],
    company_id: uuid.UUID,
    brand_code: str,
    brand_profile_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    code = str(brand_code or '').strip().upper()
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT c.company_id, c.code AS company_code, c.display_name AS company_name,
                   b.brand_id, b.code AS brand_code, b.name AS brand_name,
                   b.is_active AS brand_is_active, bp.brand_profile_id,
                   bp.display_name AS brand_profile_name
            FROM perfect_catalog.company AS c
            JOIN perfect_catalog.brand AS b ON b.company_id=c.company_id
            LEFT JOIN perfect_catalog.brand_profile AS bp
              ON bp.brand_profile_id=b.brand_profile_id
            WHERE c.company_id=%s AND c.is_active=true AND b.code=%s
              AND (%s::uuid IS NULL OR bp.brand_profile_id=%s)
            """,
            (company_id, code, brand_profile_id, brand_profile_id),
        )
        row = cursor.fetchone()
    if row is None or not row['brand_is_active']:
        raise ValueError('La Brand no existe, está inactiva o no pertenece a la Company activa.')
    if not is_company_brand_allowed(row['company_code'], row['brand_code']):
        raise ValueError('La combinación Company/Brand no está autorizada para importar.')
    # En PDM, llegar hasta aquí ya prueba que la Brand existe, está activa
    # y pertenece a la Company. El importador no crea Brands automáticamente.
    return dict(row)