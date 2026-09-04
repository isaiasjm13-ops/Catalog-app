from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .canonical import canonical_sha256
from .config import DatabaseConfig
from .image_archive_index import normalize_image_key, split_variant_suffix
from .intake_promotion import _actor, _reason

MATCH_ALGORITHM = "exact-approved-reference-v3"
MATCH_NAMESPACE = uuid.UUID("31173b46-b264-4bf7-91ef-fbbd62ace671")


def exact_image_candidates(
    entries: list[dict[str, Any]], references: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Empareja por nombre de archivo exacto. `REF-1234.jpg` es la foto principal; un sufijo
    numérico (`REF-1234-2.jpg`) o de una sola letra (`REF-1234-B.jpg`, o `A` para la principal)
    es una foto adicional de la misma referencia, no otro producto."""
    references_by_key: dict[str, list[dict[str, Any]]] = {}
    for reference in references:
        key = normalize_image_key(str(reference["value_original"]))
        if key:
            references_by_key.setdefault(key, []).append(reference)
    candidates: list[dict[str, Any]] = []
    for entry in entries:
        lookup_key = str(entry["lookup_key"])
        matches = references_by_key.get(lookup_key)
        variant_index: int | None = None
        if not matches:
            base_key, suffix = split_variant_suffix(lookup_key)
            # base_key != lookup_key means a suffix WAS recognized, even when it resolves to
            # None (the "A" letter, or no suffix, both mean "this is the main photo") — using
            # `suffix is not None` here would wrongly skip the "A" case, since its value IS None.
            if base_key != lookup_key:
                matches = references_by_key.get(base_key)
                variant_index = suffix
        for reference in matches or []:
            evidence = {
                "algorithm": MATCH_ALGORITHM,
                "image_archive_entry_id": str(entry["image_archive_entry_id"]),
                "content_sha256": str(entry["content_sha256"]),
                "lookup_key": str(entry["lookup_key"]),
                "product_reference_id": str(reference["product_reference_id"]),
                "value_normalized": str(reference["value_normalized"]),
                "product_template_id": str(reference["product_template_id"]),
                "product_variant_id": str(reference["product_variant_id"]) if reference.get("product_variant_id") else None,
                "variant_index": variant_index,
            }
            candidate_id = uuid.uuid5(
                MATCH_NAMESPACE,
                f"{entry['image_archive_entry_id']}:{reference['product_reference_id']}",
            )
            candidates.append({
                **evidence,
                "image_product_candidate_id": candidate_id,
                "evidence_sha256": canonical_sha256(evidence),
                "confidence": 1,
            })
    return candidates


def generate_image_candidates(
    image_archive_index_id: uuid.UUID, config: DatabaseConfig, password: str,
    *, actor: str, reason: str, company_id: uuid.UUID,
) -> dict[str, Any]:
    actor, reason = _actor(actor), _reason(reason)
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 2))", (str(image_archive_index_id),))
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """SELECT e.image_archive_entry_id, e.content_sha256, e.lookup_key
                   FROM perfect_catalog.image_archive_entry AS e
                   JOIN perfect_catalog.image_archive_index AS i USING (image_archive_index_id)
                   JOIN perfect_catalog.intake_submission AS s USING (intake_submission_id)
                   WHERE e.image_archive_index_id=%s AND s.company_id=%s
                   ORDER BY e.entry_order""",
                (image_archive_index_id, company_id),
            )
            entries = [dict(row) for row in cursor.fetchall()]
            if not entries:
                raise ValueError("No existe el índice de imágenes o no contiene entradas.")
            cursor.execute(
                """
                SELECT product_reference_id, product_template_id, product_variant_id,
                       value_original, value_normalized
                FROM perfect_catalog.product_reference
                JOIN perfect_catalog.brand AS b USING (brand_id)
                WHERE reference_type='internal' AND is_primary=true AND review_status='approved'
                  AND b.company_id=%s
                """,
                (company_id,),
            )
            references = [dict(row) for row in cursor.fetchall()]
        candidates = exact_image_candidates(entries, references)
        now = datetime.now(UTC)
        inserted = 0
        with connection.cursor() as cursor:
            for candidate in candidates:
                cursor.execute(
                    """
                    INSERT INTO perfect_catalog.image_product_candidate (
                        image_product_candidate_id, image_archive_entry_id,
                        product_reference_id, product_template_id, product_variant_id,
                        algorithm, confidence, evidence_sha256, generated_by, reason, generated_at,
                        variant_index
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (image_archive_entry_id, product_reference_id) DO NOTHING
                    """,
                    (candidate["image_product_candidate_id"], candidate["image_archive_entry_id"],
                     candidate["product_reference_id"], candidate["product_template_id"],
                     candidate["product_variant_id"], MATCH_ALGORITHM, candidate["confidence"],
                     candidate["evidence_sha256"], actor, reason, now, candidate["variant_index"]),
                )
                inserted += cursor.rowcount
        return {"status": "generated", "candidate_count": len(candidates), "inserted_count": inserted}


def list_image_candidates(
    config: DatabaseConfig, password: str, *, limit: int = 100, offset: int = 0,
    company_id: uuid.UUID,
) -> dict[str, Any]:
    if limit < 1 or limit > 200 or offset < 0:
        raise ValueError("Paginación inválida.")
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT c.image_product_candidate_id, c.evidence_sha256, c.confidence, c.variant_index,
                       e.original_filename, e.member_path, e.lookup_key, e.content_sha256,
                       r.value_original AS reference, p.name_original AS product_name,
                       c.product_template_id, c.product_variant_id,
                       d.decision, d.decided_by, d.decided_at,
                       COALESCE(m.approved_image_materialization_id, v.approved_image_variant_id) AS approved_image_materialization_id,
                       COALESCE(m.storage_relpath, v.storage_relpath) AS storage_relpath,
                       count(*) OVER () AS filtered_count,
                       count(*) FILTER (WHERE d.image_product_decision_id IS NULL) OVER () AS pending_count
                       , count(*) FILTER (
                           WHERE d.decision='approved'
                             AND ((c.variant_index IS NULL AND m.approved_image_materialization_id IS NULL)
                                  OR (c.variant_index IS NOT NULL AND v.approved_image_variant_id IS NULL))
                         ) OVER () AS approved_unmaterialized_count
                FROM perfect_catalog.image_product_candidate AS c
                JOIN perfect_catalog.image_archive_entry AS e ON e.image_archive_entry_id=c.image_archive_entry_id
                JOIN perfect_catalog.image_archive_index AS i ON i.image_archive_index_id=e.image_archive_index_id
                JOIN perfect_catalog.intake_submission AS s ON s.intake_submission_id=i.intake_submission_id
                JOIN perfect_catalog.product_reference AS r ON r.product_reference_id=c.product_reference_id
                JOIN perfect_catalog.product_template AS p ON p.product_template_id=c.product_template_id
                LEFT JOIN perfect_catalog.image_product_decision AS d ON d.image_product_candidate_id=c.image_product_candidate_id
                LEFT JOIN perfect_catalog.approved_image_materialization AS m ON m.image_product_candidate_id=c.image_product_candidate_id
                LEFT JOIN perfect_catalog.approved_image_variant AS v ON v.image_product_candidate_id=c.image_product_candidate_id
                WHERE s.company_id=%s
                ORDER BY c.generated_at DESC, c.image_product_candidate_id
                LIMIT %s OFFSET %s
                """,
                (company_id, limit, offset),
            )
            rows = [dict(row) for row in cursor.fetchall()]
    count = int(rows[0].pop("filtered_count")) if rows else 0
    pending_count = int(rows[0].pop("pending_count")) if rows else 0
    approved_unmaterialized_count = int(rows[0].pop("approved_unmaterialized_count")) if rows else 0
    for row in rows[1:]:
        row.pop("filtered_count", None)
        row.pop("pending_count", None)
        row.pop("approved_unmaterialized_count", None)
    return {"items": rows, "filtered_count": count, "pending_count": pending_count,
            "approved_unmaterialized_count": approved_unmaterialized_count,
            "limit": limit, "offset": offset}


def list_unlinked_image_entries(
    config: DatabaseConfig, password: str, *, limit: int = 100, offset: int = 0,
    company_id: uuid.UUID,
) -> dict[str, Any]:
    """Fotos indexadas que quedaron invisibles hasta ahora: sin ningún candidato de coincidencia
    (su nombre de archivo no correspondió a ninguna referencia aprobada) o marcadas ambiguas
    (dos archivos del mismo ZIP normalizan al mismo nombre). Ninguna se materializa ni se
    rechaza aquí; esto es solo para que el operador las vea y decida qué hacer manualmente."""
    if limit < 1 or limit > 200 or offset < 0:
        raise ValueError("Paginación inválida.")
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT e.image_archive_entry_id, e.original_filename, e.lookup_key,
                       e.match_status, e.conflict_count, e.content_sha256, e.indexed_at,
                       count(*) OVER () AS filtered_count
                FROM perfect_catalog.image_archive_entry AS e
                JOIN perfect_catalog.image_archive_index AS i
                  ON i.image_archive_index_id=e.image_archive_index_id
                JOIN perfect_catalog.intake_submission AS s
                  ON s.intake_submission_id=i.intake_submission_id
                WHERE s.company_id=%s
                  AND (
                    e.match_status='ambiguous'
                    OR NOT EXISTS (
                      SELECT 1 FROM perfect_catalog.image_product_candidate AS c
                      WHERE c.image_archive_entry_id=e.image_archive_entry_id
                    )
                  )
                ORDER BY e.indexed_at DESC, e.image_archive_entry_id
                LIMIT %s OFFSET %s
                """,
                (company_id, limit, offset),
            )
            rows = [dict(row) for row in cursor.fetchall()]
    count = int(rows[0].pop("filtered_count")) if rows else 0
    for row in rows[1:]:
        row.pop("filtered_count", None)
    for row in rows:
        row["image_archive_entry_id"] = str(row["image_archive_entry_id"])
        row["indexed_at"] = row["indexed_at"].isoformat()
    return {"items": rows, "filtered_count": count, "limit": limit, "offset": offset}


def decide_image_candidate(
    candidate_id: uuid.UUID, evidence_sha256: str, decision: str,
    actor: str, reason: str, config: DatabaseConfig, password: str,
    *, company_id: uuid.UUID,
) -> dict[str, Any]:
    actor, reason = _actor(actor), _reason(reason)
    if decision not in {"approved", "rejected"}:
        raise ValueError("Decisión de imagen inválida.")
    if len(evidence_sha256) != 64:
        raise ValueError("evidence_sha256 inválido.")
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 4))",
            (str(candidate_id),),
        )
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """SELECT c.evidence_sha256
                   FROM perfect_catalog.image_product_candidate AS c
                   JOIN perfect_catalog.image_archive_entry AS e
                     ON e.image_archive_entry_id=c.image_archive_entry_id
                   JOIN perfect_catalog.image_archive_index AS i
                     ON i.image_archive_index_id=e.image_archive_index_id
                   JOIN perfect_catalog.intake_submission AS s
                     ON s.intake_submission_id=i.intake_submission_id
                   WHERE c.image_product_candidate_id=%s AND s.company_id=%s""",
                (candidate_id, company_id),
            )
            candidate = cursor.fetchone()
            if candidate is None:
                raise ValueError("No existe el candidato de imagen.")
            if candidate["evidence_sha256"] != evidence_sha256:
                raise PermissionError("La evidencia del candidato cambió.")
            cursor.execute(
                "SELECT decision, candidate_evidence_sha256 FROM perfect_catalog.image_product_decision WHERE image_product_candidate_id=%s",
                (candidate_id,),
            )
            existing = cursor.fetchone()
            if existing:
                if existing["decision"] == decision and existing["candidate_evidence_sha256"] == evidence_sha256:
                    return {"status": f"already_{decision}"}
                raise PermissionError("El candidato ya tiene una decisión diferente.")
            cursor.execute(
                """
                INSERT INTO perfect_catalog.image_product_decision (
                    image_product_decision_id, image_product_candidate_id, decision,
                    candidate_evidence_sha256, decided_by, reason, decided_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (uuid.uuid4(), candidate_id, decision, evidence_sha256, actor, reason, datetime.now(UTC)),
            )
    return {"status": decision}


def decide_image_candidates_bulk(
    expected_count: int, decision: str, actor: str, reason: str,
    config: DatabaseConfig, password: str, *, company_id: uuid.UUID,
    max_items: int = 500,
) -> dict[str, Any]:
    """Decide el conjunto pendiente exacto en una transacción; nunca materializa archivos."""
    actor, reason = _actor(actor), _reason(reason)
    if decision not in {"approved", "rejected"}:
        raise ValueError("Decisión de imagen inválida.")
    if not 1 <= expected_count <= max_items:
        raise ValueError(f"expected_count debe estar entre 1 y {max_items}.")
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 3))",
            ("perfect_catalog.image_product_candidate.bulk_decision",),
        )
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT c.image_product_candidate_id, c.evidence_sha256
                FROM perfect_catalog.image_product_candidate AS c
                JOIN perfect_catalog.image_archive_entry AS e
                  ON e.image_archive_entry_id=c.image_archive_entry_id
                JOIN perfect_catalog.image_archive_index AS i
                  ON i.image_archive_index_id=e.image_archive_index_id
                JOIN perfect_catalog.intake_submission AS s
                  ON s.intake_submission_id=i.intake_submission_id
                LEFT JOIN perfect_catalog.image_product_decision AS d
                  ON d.image_product_candidate_id=c.image_product_candidate_id
                WHERE d.image_product_decision_id IS NULL AND s.company_id=%s
                ORDER BY c.generated_at, c.image_product_candidate_id
                LIMIT %s
                """,
                (company_id, max_items + 1),
            )
            candidates = [dict(row) for row in cursor.fetchall()]
            if len(candidates) != expected_count:
                raise PermissionError(
                    "La cantidad pendiente cambió; recarga antes de decidir el lote."
                )
            now = datetime.now(UTC)
            for candidate in candidates:
                cursor.execute(
                    """
                    INSERT INTO perfect_catalog.image_product_decision (
                        image_product_decision_id, image_product_candidate_id, decision,
                        candidate_evidence_sha256, decided_by, reason, decided_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (uuid.uuid4(), candidate["image_product_candidate_id"], decision,
                     candidate["evidence_sha256"], actor, reason, now),
                )
    return {
        "status": "bulk_approved" if decision == "approved" else "bulk_rejected",
        "count": expected_count,
    }
