from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .canonical import canonical_sha256
from .config import DatabaseConfig
from .image_archive_index import normalize_image_key
from .intake_promotion import _actor, _reason

MATCH_ALGORITHM = "exact-approved-reference-v1"
MATCH_NAMESPACE = uuid.UUID("31173b46-b264-4bf7-91ef-fbbd62ace671")


def exact_image_candidates(
    entries: list[dict[str, Any]], references: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    references_by_key: dict[str, list[dict[str, Any]]] = {}
    for reference in references:
        key = normalize_image_key(str(reference["value_original"]))
        if key:
            references_by_key.setdefault(key, []).append(reference)
    candidates: list[dict[str, Any]] = []
    for entry in entries:
        for reference in references_by_key.get(str(entry["lookup_key"]), []):
            evidence = {
                "algorithm": MATCH_ALGORITHM,
                "image_archive_entry_id": str(entry["image_archive_entry_id"]),
                "content_sha256": str(entry["content_sha256"]),
                "lookup_key": str(entry["lookup_key"]),
                "product_reference_id": str(reference["product_reference_id"]),
                "value_normalized": str(reference["value_normalized"]),
                "product_template_id": str(reference["product_template_id"]),
                "product_variant_id": str(reference["product_variant_id"]) if reference.get("product_variant_id") else None,
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
    *, actor: str, reason: str,
) -> dict[str, Any]:
    actor, reason = _actor(actor), _reason(reason)
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 2))", (str(image_archive_index_id),))
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                "SELECT image_archive_entry_id, content_sha256, lookup_key FROM perfect_catalog.image_archive_entry WHERE image_archive_index_id=%s ORDER BY entry_order",
                (image_archive_index_id,),
            )
            entries = [dict(row) for row in cursor.fetchall()]
            if not entries:
                raise ValueError("No existe el índice de imágenes o no contiene entradas.")
            cursor.execute(
                """
                SELECT product_reference_id, product_template_id, product_variant_id,
                       value_original, value_normalized
                FROM perfect_catalog.product_reference
                WHERE reference_type='internal' AND is_primary=true AND review_status='approved'
                """
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
                        algorithm, confidence, evidence_sha256, generated_by, reason, generated_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (image_archive_entry_id, product_reference_id) DO NOTHING
                    """,
                    (candidate["image_product_candidate_id"], candidate["image_archive_entry_id"],
                     candidate["product_reference_id"], candidate["product_template_id"],
                     candidate["product_variant_id"], MATCH_ALGORITHM, candidate["confidence"],
                     candidate["evidence_sha256"], actor, reason, now),
                )
                inserted += cursor.rowcount
        return {"status": "generated", "candidate_count": len(candidates), "inserted_count": inserted}


def list_image_candidates(
    config: DatabaseConfig, password: str, *, limit: int = 100, offset: int = 0
) -> dict[str, Any]:
    if limit < 1 or limit > 200 or offset < 0:
        raise ValueError("Paginación inválida.")
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT c.image_product_candidate_id, c.evidence_sha256, c.confidence,
                       e.original_filename, e.member_path, e.lookup_key, e.content_sha256,
                       r.value_original AS reference, p.name_original AS product_name,
                       c.product_template_id, c.product_variant_id,
                       d.decision, d.decided_by, d.decided_at,
                       m.approved_image_materialization_id, m.storage_relpath,
                       count(*) OVER () AS filtered_count,
                       count(*) FILTER (WHERE d.image_product_decision_id IS NULL) OVER () AS pending_count
                FROM perfect_catalog.image_product_candidate AS c
                JOIN perfect_catalog.image_archive_entry AS e ON e.image_archive_entry_id=c.image_archive_entry_id
                JOIN perfect_catalog.product_reference AS r ON r.product_reference_id=c.product_reference_id
                JOIN perfect_catalog.product_template AS p ON p.product_template_id=c.product_template_id
                LEFT JOIN perfect_catalog.image_product_decision AS d ON d.image_product_candidate_id=c.image_product_candidate_id
                LEFT JOIN perfect_catalog.approved_image_materialization AS m ON m.image_product_candidate_id=c.image_product_candidate_id
                ORDER BY c.generated_at DESC, c.image_product_candidate_id
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            rows = [dict(row) for row in cursor.fetchall()]
    count = int(rows[0].pop("filtered_count")) if rows else 0
    pending_count = int(rows[0].pop("pending_count")) if rows else 0
    for row in rows[1:]:
        row.pop("filtered_count", None)
        row.pop("pending_count", None)
    return {"items": rows, "filtered_count": count, "pending_count": pending_count,
            "limit": limit, "offset": offset}


def decide_image_candidate(
    candidate_id: uuid.UUID, evidence_sha256: str, decision: str,
    actor: str, reason: str, config: DatabaseConfig, password: str,
) -> dict[str, Any]:
    actor, reason = _actor(actor), _reason(reason)
    if decision not in {"approved", "rejected"}:
        raise ValueError("Decisión de imagen inválida.")
    if len(evidence_sha256) != 64:
        raise ValueError("evidence_sha256 inválido.")
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                "SELECT evidence_sha256 FROM perfect_catalog.image_product_candidate WHERE image_product_candidate_id=%s FOR UPDATE",
                (candidate_id,),
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
    config: DatabaseConfig, password: str, *, max_items: int = 500,
) -> dict[str, Any]:
    """Decide el conjunto pendiente exacto en una transacción; nunca materializa archivos."""
    actor, reason = _actor(actor), _reason(reason)
    if decision not in {"approved", "rejected"}:
        raise ValueError("Decisión de imagen inválida.")
    if not 1 <= expected_count <= max_items:
        raise ValueError(f"expected_count debe estar entre 1 y {max_items}.")
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT c.image_product_candidate_id, c.evidence_sha256
                FROM perfect_catalog.image_product_candidate AS c
                LEFT JOIN perfect_catalog.image_product_decision AS d
                  ON d.image_product_candidate_id=c.image_product_candidate_id
                WHERE d.image_product_decision_id IS NULL
                ORDER BY c.generated_at, c.image_product_candidate_id
                LIMIT %s
                FOR UPDATE OF c
                """,
                (max_items + 1,),
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
