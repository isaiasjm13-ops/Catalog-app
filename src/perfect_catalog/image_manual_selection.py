"""Selección manual de fotos: el operador elige a qué producto pertenece una foto que no
coincidió sola (ambigua o sin coincidencia exacta). Idea tomada de Kairo OmegaCreator
(elegir entre miniaturas), pero conservando la auditoría append-only de esta consola."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .canonical import canonical_sha256
from .config import DatabaseConfig
from .intake_promotion import _actor, _reason

MANUAL_ALGORITHM = "operator-selected-v1"
MANUAL_NAMESPACE = uuid.UUID("5d0c1a7e-7a4b-4c9e-9b0e-2f7d8c1a4e63")
MANUAL_KINDS = {"main", "additional"}


def search_product_references(
    query: str, config: DatabaseConfig, password: str, *, company_id: uuid.UUID, limit: int = 8,
) -> list[dict[str, Any]]:
    """Busca productos aprobados de la compañía por referencia o nombre. Solo lectura; indica
    si el producto ya tiene una foto principal vigente."""
    query = str(query or "").strip()
    if len(query) < 2:
        raise ValueError("Escribe al menos 2 caracteres para buscar.")
    if len(query) > 80 or not 1 <= limit <= 20:
        raise ValueError("Búsqueda inválida.")
    pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT r.product_reference_id, r.value_original AS reference,
                       p.name_original AS product_name,
                       EXISTS (
                         SELECT 1 FROM perfect_catalog.image_product_candidate AS c
                         LEFT JOIN perfect_catalog.image_product_decision AS d
                           ON d.image_product_candidate_id=c.image_product_candidate_id
                         WHERE COALESCE(c.product_variant_id, c.product_template_id)
                               = COALESCE(r.product_variant_id, r.product_template_id)
                           AND c.variant_index IS NULL
                           AND d.decision IS DISTINCT FROM 'rejected'
                       ) AS has_main_photo
                FROM perfect_catalog.product_reference AS r
                JOIN perfect_catalog.brand AS b USING (brand_id)
                JOIN perfect_catalog.product_template AS p ON p.product_template_id=r.product_template_id
                WHERE r.reference_type='internal' AND r.is_primary=true AND r.review_status='approved'
                  AND b.company_id=%s
                  AND (r.value_original ILIKE %s OR p.name_original ILIKE %s)
                ORDER BY r.value_original
                LIMIT %s
                """,
                (company_id, pattern, pattern, limit),
            )
            rows = [dict(row) for row in cursor.fetchall()]
    for row in rows:
        row["product_reference_id"] = str(row["product_reference_id"])
    return rows


def assign_image_manually(
    entry_id: uuid.UUID, product_reference_id: uuid.UUID, kind: str, actor: str,
    config: DatabaseConfig, password: str, *, company_id: uuid.UUID,
) -> dict[str, Any]:
    """Asigna una foto a un producto elegido por el operador.

    Crea, en una sola transacción, un candidato `operator-selected-v1` y su decisión `approved`
    (append-only, con el actor). No copia el archivo: la materialización sigue siendo el paso
    verificable posterior ("Preparar coincidencias exactas"). kind='main' es la foto principal;
    'additional' toma el siguiente índice libre de foto adicional (2, 3, ...)."""
    actor = _actor(actor)
    if kind not in MANUAL_KINDS:
        raise ValueError("Tipo de foto inválido.")
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 5))", (str(product_reference_id),),
        )
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """SELECT e.image_archive_entry_id, e.content_sha256, e.lookup_key
                   FROM perfect_catalog.image_archive_entry AS e
                   JOIN perfect_catalog.image_archive_index AS i USING (image_archive_index_id)
                   JOIN perfect_catalog.intake_submission AS s USING (intake_submission_id)
                   WHERE e.image_archive_entry_id=%s AND s.company_id=%s""",
                (entry_id, company_id),
            )
            entry = cursor.fetchone()
            if entry is None:
                raise ValueError("No existe la foto indicada.")
            cursor.execute(
                """SELECT r.product_reference_id, r.product_template_id, r.product_variant_id,
                          r.value_original, r.value_normalized
                   FROM perfect_catalog.product_reference AS r
                   JOIN perfect_catalog.brand AS b USING (brand_id)
                   WHERE r.product_reference_id=%s AND r.reference_type='internal'
                     AND r.is_primary=true AND r.review_status='approved' AND b.company_id=%s""",
                (product_reference_id, company_id),
            )
            reference = cursor.fetchone()
            if reference is None:
                raise ValueError("El producto indicado no existe o no está aprobado.")
            cursor.execute(
                """SELECT 1 FROM perfect_catalog.image_product_candidate
                   WHERE image_archive_entry_id=%s AND product_reference_id=%s""",
                (entry_id, product_reference_id),
            )
            if cursor.fetchone() is not None:
                raise ValueError(
                    "Esa foto ya tiene una propuesta para ese producto; revísala en la lista de asociaciones."
                )
            cursor.execute(
                """SELECT max(c.variant_index) AS max_variant,
                          COALESCE(bool_or(c.variant_index IS NULL), false) AS has_main
                   FROM perfect_catalog.image_product_candidate AS c
                   LEFT JOIN perfect_catalog.image_product_decision AS d
                     ON d.image_product_candidate_id=c.image_product_candidate_id
                   WHERE COALESCE(c.product_variant_id, c.product_template_id)
                         = COALESCE(%s::uuid, %s::uuid)
                     AND d.decision IS DISTINCT FROM 'rejected'""",
                (reference["product_variant_id"], reference["product_template_id"]),
            )
            taken = cursor.fetchone() or {}
            if kind == "main":
                if taken.get("has_main"):
                    raise ValueError("Ese producto ya tiene foto principal; elige 'foto adicional'.")
                variant_index = None
            else:
                variant_index = max(int(taken.get("max_variant") or 1), 1) + 1
            evidence = {
                "algorithm": MANUAL_ALGORITHM,
                "image_archive_entry_id": str(entry["image_archive_entry_id"]),
                "content_sha256": str(entry["content_sha256"]),
                "lookup_key": str(entry["lookup_key"]),
                "product_reference_id": str(reference["product_reference_id"]),
                "value_normalized": str(reference["value_normalized"]),
                "product_template_id": str(reference["product_template_id"]),
                "product_variant_id": (
                    str(reference["product_variant_id"]) if reference["product_variant_id"] else None
                ),
                "variant_index": variant_index,
                "selected_by": actor,
            }
            evidence_sha256 = canonical_sha256(evidence)
            candidate_id = uuid.uuid5(MANUAL_NAMESPACE, f"{entry_id}:{product_reference_id}")
            reason = _reason(f"Selección manual del operador: foto asignada a {reference['value_original']}")
            now = datetime.now(UTC)
            cursor.execute(
                """
                INSERT INTO perfect_catalog.image_product_candidate (
                    image_product_candidate_id, image_archive_entry_id,
                    product_reference_id, product_template_id, product_variant_id,
                    algorithm, confidence, evidence_sha256, generated_by, reason, generated_at,
                    variant_index
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (candidate_id, entry_id, product_reference_id, reference["product_template_id"],
                 reference["product_variant_id"], MANUAL_ALGORITHM, 1, evidence_sha256, actor,
                 reason, now, variant_index),
            )
            cursor.execute(
                """
                INSERT INTO perfect_catalog.image_product_decision (
                    image_product_decision_id, image_product_candidate_id, decision,
                    candidate_evidence_sha256, decided_by, reason, decided_at
                ) VALUES (%s,%s,'approved',%s,%s,%s,%s)
                """,
                (uuid.uuid4(), candidate_id, evidence_sha256, actor, reason, now),
            )
    return {
        "status": "assigned", "image_product_candidate_id": str(candidate_id),
        "reference": str(reference["value_original"]), "variant_index": variant_index,
    }
