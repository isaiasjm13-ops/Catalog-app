from __future__ import annotations

import uuid
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row


def is_company_brand_allowed(company_code: str, brand_code: str) -> bool:
    company = str(company_code or '').strip().upper()
    brand = str(brand_code or '').strip().upper()
    if company == 'MASAKI':
        return False
    if company == 'NATSUKI':
        return brand == 'NATSUKI'
    if company == 'KMC':
        return brand == 'A1'
    if company == 'PDM':
        return bool(brand)
    return brand in {'PERFECT', 'MASAKI', 'EXACTCARS'}


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