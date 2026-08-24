from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .application import _load_plan_items
from .canonical import canonical_sha256, json_compatible
from .config import DatabaseConfig
from .publication import _load_applied_plan


REVIEW_ALGORITHM = "catalog-identity-review-v1"
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
DECISIONS = frozenset({"approve", "reject"})
MAX_REVIEW_QUEUE_ITEMS = 5_000
REVIEW_STATES = frozenset({"all", "pending", "approved", "rejected", "inconsistent"})


def _require_text(value: str, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} no puede estar vacío.")
    return text


def _require_sha256(value: str, label: str) -> str:
    digest = str(value or "").strip().lower()
    if not SHA256_PATTERN.fullmatch(digest):
        raise ValueError(f"{label} debe contener 64 caracteres hexadecimales.")
    return digest


def _require_decision(value: str) -> str:
    decision = str(value or "").strip().lower()
    if decision not in DECISIONS:
        raise ValueError("decision debe ser 'approve' o 'reject'.")
    return decision


def _identify_target(
    connection: Connection[Any], target_id: uuid.UUID
) -> str:
    row = connection.execute(
        """
        SELECT
            (SELECT count(*) FROM perfect_catalog.product_template
             WHERE product_template_id=%s),
            (SELECT count(*) FROM perfect_catalog.product_variant
             WHERE product_variant_id=%s)
        """,
        (target_id, target_id),
    ).fetchone()
    total = int(row[0]) + int(row[1])
    if total == 0:
        raise ValueError(f"No existe la identidad de producto {target_id}.")
    if total != 1:
        raise RuntimeError("El UUID colisiona entre template y variante.")
    return "product_template" if row[0] else "product_variant"


def _load_review_target(
    connection: Connection[Any], target_id: uuid.UUID, *, lock: bool
) -> dict[str, Any]:
    identity_type = _identify_target(connection, target_id)
    if lock:
        id_column = (
            "product_template_id"
            if identity_type == "product_template"
            else "product_variant_id"
        )
        connection.execute(
            f"SELECT 1 FROM perfect_catalog.{identity_type} "
            f"WHERE {id_column}=%s FOR UPDATE",
            (target_id,),
        )

    with connection.cursor(row_factory=dict_row) as cursor:
        if identity_type == "product_template":
            cursor.execute(
                """
                SELECT 'product_template' AS identity_type,
                       p.product_template_id AS public_id,
                       p.product_template_id, NULL::uuid AS product_variant_id,
                       p.catalog_status, p.catalog_status AS template_status,
                       p.name_original, NULL::text AS variant_name,
                       p.source_system_id, p.brand_id, b.name AS brand_name,
                       p.last_confirmed_batch_id AS source_import_batch_id,
                       p.created_from_staging_row_id AS staging_row_id,
                       sr.source_row_number
                FROM perfect_catalog.product_template AS p
                JOIN perfect_catalog.brand AS b ON b.brand_id=p.brand_id
                JOIN perfect_catalog.staging_row AS sr
                  ON sr.staging_row_id=p.created_from_staging_row_id
                WHERE p.product_template_id=%s
                """,
                (target_id,),
            )
        else:
            cursor.execute(
                """
                SELECT 'product_variant' AS identity_type,
                       v.product_variant_id AS public_id,
                       p.product_template_id, v.product_variant_id,
                       v.catalog_status, p.catalog_status AS template_status,
                       p.name_original, v.variant_name,
                       p.source_system_id, p.brand_id, b.name AS brand_name,
                       p.last_confirmed_batch_id AS source_import_batch_id,
                       v.created_from_staging_row_id AS staging_row_id,
                       sr.source_row_number
                FROM perfect_catalog.product_variant AS v
                JOIN perfect_catalog.product_template AS p
                  ON p.product_template_id=v.product_template_id
                JOIN perfect_catalog.brand AS b ON b.brand_id=p.brand_id
                JOIN perfect_catalog.staging_row AS sr
                  ON sr.staging_row_id=v.created_from_staging_row_id
                WHERE v.product_variant_id=%s
                """,
                (target_id,),
            )
        target_row = cursor.fetchone()
    if target_row is None:
        raise RuntimeError("La identidad desapareció durante la revisión.")
    target = dict(target_row)

    suffix = " FOR UPDATE" if lock else ""
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            f"""
            SELECT product_reference_id, reference_type, value_original,
                   value_normalized, is_primary, review_status,
                   reviewed_by, reviewed_at, review_note, staging_row_id
            FROM perfect_catalog.product_reference
            WHERE product_template_id=%s
              AND product_variant_id IS NOT DISTINCT FROM %s
              AND reference_type='internal' AND is_primary=true
            ORDER BY product_reference_id{suffix}
            """,
            (target["product_template_id"], target["product_variant_id"]),
        )
        references = [dict(row) for row in cursor.fetchall()]
    if len(references) != 1:
        raise RuntimeError(
            "La identidad requiere exactamente una referencia interna primaria para revisión."
        )
    target["reference"] = references[0]
    return target


def review_evidence(
    target: dict[str, Any], plan: dict[str, Any]
) -> dict[str, Any]:
    reference = target["reference"]
    return {
        "algorithm": REVIEW_ALGORITHM,
        "source_plan_id": plan["import_plan_id"],
        "source_plan_fingerprint_sha256": plan["approval_fingerprint_sha256"],
        "source_import_batch_id": plan["import_batch_id"],
        "identity_type": target["identity_type"],
        "public_id": target["public_id"],
        "product_template_id": target["product_template_id"],
        "product_variant_id": target["product_variant_id"],
        "source_system_id": target["source_system_id"],
        "brand_id": target["brand_id"],
        "brand_name": target["brand_name"],
        "name_original": target["name_original"],
        "variant_name": target["variant_name"],
        "catalog_status": target["catalog_status"],
        "template_status": target["template_status"],
        "source_row_number": target["source_row_number"],
        "reference": {
            "product_reference_id": reference["product_reference_id"],
            "reference_type": reference["reference_type"],
            "value_original": reference["value_original"],
            "value_normalized": reference["value_normalized"],
            "is_primary": reference["is_primary"],
            "review_status": reference["review_status"],
        },
    }


def review_evidence_sha256(target: dict[str, Any], plan: dict[str, Any]) -> str:
    return canonical_sha256(review_evidence(target, plan))


def _require_review_state(value: str) -> str:
    state = str(value or "all").strip().lower()
    if state not in REVIEW_STATES:
        raise ValueError(f"Estado de revisión desconocido: {state!r}.")
    return state


def _review_target_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "identity_type": row["identity_type"],
        "public_id": row["public_id"],
        "product_template_id": row["product_template_id"],
        "product_variant_id": row["product_variant_id"],
        "catalog_status": row["catalog_status"],
        "template_status": row["template_status"],
        "name_original": row["name_original"],
        "variant_name": row["variant_name"],
        "source_system_id": row["source_system_id"],
        "brand_id": row["brand_id"],
        "brand_name": row["brand_name"],
        "source_import_batch_id": row["source_import_batch_id"],
        "staging_row_id": row["staging_row_id"],
        "source_row_number": row["source_row_number"],
        "reference": {
            "product_reference_id": row["product_reference_id"],
            "reference_type": row["reference_type"],
            "value_original": row["value_original"],
            "value_normalized": row["value_normalized"],
            "is_primary": row["is_primary"],
            "review_status": row["review_status"],
        },
    }


REVIEW_ROWS_SQL = """
WITH target_ids AS (
    SELECT DISTINCT planned_product_template_id, planned_product_variant_id
    FROM perfect_catalog.import_plan_item
    WHERE import_plan_id=%s AND operation_type='create'
), review_rows AS (
    SELECT
        CASE WHEN t.planned_product_variant_id IS NULL
             THEN 'product_template' ELSE 'product_variant' END AS identity_type,
        COALESCE(t.planned_product_variant_id, t.planned_product_template_id) AS public_id,
        t.planned_product_template_id AS product_template_id,
        t.planned_product_variant_id AS product_variant_id,
        CASE WHEN t.planned_product_variant_id IS NULL
             THEN p.catalog_status ELSE v.catalog_status END AS catalog_status,
        p.catalog_status AS template_status,
        p.name_original, v.variant_name, p.source_system_id, p.brand_id,
        b.name AS brand_name, p.last_confirmed_batch_id AS source_import_batch_id,
        COALESCE(v.created_from_staging_row_id, p.created_from_staging_row_id) AS staging_row_id,
        sr.source_row_number,
        ref.product_reference_id, ref.reference_type, ref.value_original,
        ref.value_normalized, ref.is_primary, ref.review_status,
        COALESCE(ref.reference_count, 0) AS reference_count
    FROM target_ids AS t
    LEFT JOIN perfect_catalog.product_template AS p
      ON p.product_template_id=t.planned_product_template_id
    LEFT JOIN perfect_catalog.product_variant AS v
      ON v.product_variant_id=t.planned_product_variant_id
     AND v.product_template_id=t.planned_product_template_id
    LEFT JOIN perfect_catalog.brand AS b ON b.brand_id=p.brand_id
    LEFT JOIN perfect_catalog.staging_row AS sr
      ON sr.staging_row_id=COALESCE(
          v.created_from_staging_row_id, p.created_from_staging_row_id
      )
    LEFT JOIN LATERAL (
        SELECT pr.product_reference_id, pr.reference_type, pr.value_original,
               pr.value_normalized, pr.is_primary, pr.review_status,
               count(*) OVER () AS reference_count
        FROM perfect_catalog.product_reference AS pr
        WHERE pr.product_template_id=t.planned_product_template_id
          AND pr.product_variant_id IS NOT DISTINCT FROM t.planned_product_variant_id
          AND pr.reference_type='internal' AND pr.is_primary=true
        ORDER BY pr.product_reference_id
        LIMIT 1
    ) AS ref ON true
), classified AS (
    SELECT review_rows.*,
           CASE
             WHEN source_system_id IS NULL OR catalog_status IS NULL
               OR reference_count <> 1 THEN 'inconsistent'
             WHEN catalog_status='pending_review'
               AND COALESCE(review_status, 'pending')='pending' THEN 'pending'
             WHEN catalog_status='active' AND review_status='approved' THEN 'approved'
             WHEN catalog_status='inactive' AND review_status='rejected' THEN 'rejected'
             ELSE 'inconsistent'
           END AS review_state
    FROM review_rows
)
"""


def _review_queue_page_in_connection(
    connection: Connection[Any],
    plan_id: uuid.UUID,
    expected_fingerprint: str,
    *,
    query: str = "",
    state: str = "all",
    limit: int = 50,
    offset: int = 0,
    _max_limit: int = 500,
) -> dict[str, Any]:
    query = str(query or "").strip()
    if len(query) > 200:
        raise ValueError("La búsqueda no puede superar 200 caracteres.")
    state = _require_review_state(state)
    if not 1 <= limit <= _max_limit:
        raise ValueError(f"limit debe estar entre 1 y {_max_limit}.")
    if offset < 0:
        raise ValueError("offset no puede ser negativo.")
    plan = _load_applied_plan(
        connection, plan_id, expected_fingerprint, lock=False
    )
    plan_items = _load_plan_items(connection, plan_id)
    candidate_ids = {
        item.get("planned_product_variant_id")
        or item.get("planned_product_template_id")
        for item in plan_items
        if item["operation_type"] == "create"
    }
    candidate_ids.discard(None)
    if not candidate_ids:
        raise RuntimeError("El plan aplicado no creó identidades revisables.")

    state_clause = "" if state == "all" else "AND review_state=%s"
    filter_sql = f"""
        WHERE (
            %s='' OR COALESCE(name_original, '') ILIKE %s
            OR COALESCE(variant_name, '') ILIKE %s
            OR COALESCE(value_original, '') ILIKE %s
            OR COALESCE(value_normalized, '') ILIKE %s
            OR COALESCE(source_row_number::text, '')=%s
        )
        {state_clause}
    """
    sql = REVIEW_ROWS_SQL + f"""
        SELECT classified.*, count(*) OVER () AS filtered_count
        FROM classified
        {filter_sql}
        ORDER BY source_row_number NULLS LAST, public_id
        LIMIT %s OFFSET %s
    """
    like_query = f"%{query}%"
    params: list[Any] = [
        plan_id,
        query,
        like_query,
        like_query,
        like_query,
        like_query,
        query,
    ]
    if state != "all":
        params.append(state)
    params.extend((limit, offset))
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(sql, params)
        rows = [dict(row) for row in cursor.fetchall()]
        if rows:
            filtered_count = int(rows[0]["filtered_count"])
        else:
            cursor.execute(
                REVIEW_ROWS_SQL
                + "SELECT count(*) AS filtered_count FROM classified "
                + filter_sql,
                params[:-2],
            )
            filtered_count = int(cursor.fetchone()["filtered_count"])

    items = []
    for row in rows:
        target = _review_target_from_row(row)
        items.append(
            {
                "product_id": str(row["public_id"]),
                "identity_type": row["identity_type"],
                "name": row["name_original"],
                "variant_name": row["variant_name"],
                "reference": row["value_original"],
                "catalog_status": row["catalog_status"],
                "reference_status": row["review_status"],
                "reference_count": int(row["reference_count"]),
                "source_row_number": row["source_row_number"],
                "review_state": row["review_state"],
                "review_sha256": review_evidence_sha256(target, plan),
            }
        )
    return {
        "plan_id": str(plan_id),
        "plan_status": plan["plan_status"],
        "fingerprint": plan["approval_fingerprint_sha256"],
        "candidate_count": len(candidate_ids),
        "filtered_count": filtered_count,
        "limit": limit,
        "offset": offset,
        "query": query,
        "state": state,
        "items": items,
    }


def inspect_review_queue_page(
    plan_id: uuid.UUID,
    expected_fingerprint: str,
    config: DatabaseConfig,
    password: str,
    *,
    query: str = "",
    state: str = "all",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        return _review_queue_page_in_connection(
            connection,
            plan_id,
            expected_fingerprint,
            query=query,
            state=state,
            limit=limit,
            offset=offset,
        )


def _list_review_plans_in_connection(
    connection: Connection[Any],
    *,
    limit: int = 100,
    plan_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    if not 1 <= limit <= 500:
        raise ValueError("limit debe estar entre 1 y 500.")
    target_filter = "" if plan_id is None else "AND i.import_plan_id=%s"
    plan_filter = "" if plan_id is None else "AND p.import_plan_id=%s"
    sql = f"""
        WITH targets AS (
            SELECT DISTINCT i.import_plan_id,
                   i.planned_product_template_id,
                   i.planned_product_variant_id
            FROM perfect_catalog.import_plan_item AS i
            WHERE i.operation_type='create' {target_filter}
        ), target_states AS (
            SELECT t.import_plan_id,
                   COALESCE(t.planned_product_variant_id,
                            t.planned_product_template_id) AS public_id,
                   CASE WHEN t.planned_product_variant_id IS NULL
                        THEN p.catalog_status ELSE v.catalog_status END AS catalog_status,
                   ref.review_status, COALESCE(ref.reference_count, 0) AS reference_count
            FROM targets AS t
            LEFT JOIN perfect_catalog.product_template AS p
              ON p.product_template_id=t.planned_product_template_id
            LEFT JOIN perfect_catalog.product_variant AS v
              ON v.product_variant_id=t.planned_product_variant_id
             AND v.product_template_id=t.planned_product_template_id
            LEFT JOIN LATERAL (
                SELECT pr.review_status, count(*) OVER () AS reference_count
                FROM perfect_catalog.product_reference AS pr
                WHERE pr.product_template_id=t.planned_product_template_id
                  AND pr.product_variant_id IS NOT DISTINCT FROM t.planned_product_variant_id
                  AND pr.reference_type='internal' AND pr.is_primary=true
                ORDER BY pr.product_reference_id
                LIMIT 1
            ) AS ref ON true
        ), classified AS (
            SELECT target_states.*,
                   CASE
                     WHEN catalog_status IS NULL OR reference_count <> 1
                       THEN 'inconsistent'
                     WHEN catalog_status='pending_review'
                       AND COALESCE(review_status, 'pending')='pending' THEN 'pending'
                     WHEN catalog_status='active' AND review_status='approved' THEN 'approved'
                     WHEN catalog_status='inactive' AND review_status='rejected' THEN 'rejected'
                     ELSE 'inconsistent'
                   END AS review_state
            FROM target_states
        )
        SELECT p.import_plan_id, p.approval_fingerprint_sha256,
               p.contract_version, p.rules_version, p.applied_at, p.applied_by,
               f.original_name,
               count(c.public_id) AS candidate_count,
               count(c.public_id) FILTER (WHERE c.review_state='pending') AS pending_count,
               count(c.public_id) FILTER (WHERE c.review_state='approved') AS approved_count,
               count(c.public_id) FILTER (WHERE c.review_state='rejected') AS rejected_count,
               count(c.public_id) FILTER (WHERE c.review_state='inconsistent') AS inconsistent_count
        FROM perfect_catalog.import_plan AS p
        JOIN perfect_catalog.import_file AS f ON f.import_file_id=p.import_file_id
        JOIN classified AS c ON c.import_plan_id=p.import_plan_id
        WHERE p.plan_status='applied' {plan_filter}
        GROUP BY p.import_plan_id, p.approval_fingerprint_sha256,
                 p.contract_version, p.rules_version, p.applied_at, p.applied_by,
                 f.original_name
        ORDER BY p.applied_at DESC, p.import_plan_id DESC
        LIMIT %s
    """
    params: list[Any] = []
    if plan_id is not None:
        params.extend((plan_id, plan_id))
    params.append(limit)
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(sql, params)
        rows = [dict(row) for row in cursor.fetchall()]
    return [
        {
            **row,
            "import_plan_id": str(row["import_plan_id"]),
            "approval_fingerprint_sha256": str(
                row["approval_fingerprint_sha256"]
            ),
            "candidate_count": int(row["candidate_count"]),
            "pending_count": int(row["pending_count"]),
            "approved_count": int(row["approved_count"]),
            "rejected_count": int(row["rejected_count"]),
            "inconsistent_count": int(row["inconsistent_count"]),
        }
        for row in rows
    ]


def list_review_plans(
    config: DatabaseConfig, password: str, *, limit: int = 100
) -> list[dict[str, Any]]:
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        return _list_review_plans_in_connection(connection, limit=limit)


def get_review_plan(
    plan_id: uuid.UUID, config: DatabaseConfig, password: str
) -> dict[str, Any] | None:
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        rows = _list_review_plans_in_connection(
            connection, limit=1, plan_id=plan_id
        )
    return rows[0] if rows else None


def _assert_target_belongs_to_plan(
    target_id: uuid.UUID, items: list[dict[str, Any]]
) -> None:
    targets = {
        item.get("planned_product_variant_id")
        or item.get("planned_product_template_id")
        for item in items
        if item["operation_type"] == "create"
    }
    if target_id not in targets:
        raise PermissionError(
            f"La identidad {target_id} no fue creada por el plan aplicado indicado."
        )


def _inspect_review_queue_in_connection(
    connection: Connection[Any],
    plan_id: uuid.UUID,
    expected_fingerprint: str,
) -> dict[str, Any]:
    page = _review_queue_page_in_connection(
        connection,
        plan_id,
        expected_fingerprint,
        limit=MAX_REVIEW_QUEUE_ITEMS,
        _max_limit=MAX_REVIEW_QUEUE_ITEMS,
    )
    if page["candidate_count"] > MAX_REVIEW_QUEUE_ITEMS:
        raise RuntimeError(
            "La cola supera el limite seguro de 5000 identidades del piloto; "
            "requiere inspeccion paginada antes de continuar."
        )
    candidates = page["items"]
    queue_evidence = {
        "algorithm": REVIEW_ALGORITHM,
        "source_plan_id": plan_id,
        "source_plan_fingerprint_sha256": page["fingerprint"],
        "items": [
            {"product_id": item["product_id"], "review_sha256": item["review_sha256"]}
            for item in candidates
        ],
    }
    return {
        "plan_id": str(plan_id),
        "plan_status": page["plan_status"],
        "candidate_count": len(candidates),
        "pending_count": sum(
            item["catalog_status"] == "pending_review"
            or item["reference_status"] in (None, "pending")
            for item in candidates
        ),
        "review_queue_sha256": canonical_sha256(queue_evidence),
        "items": candidates,
    }


def inspect_review_queue(
    plan_id: uuid.UUID,
    expected_fingerprint: str,
    config: DatabaseConfig,
    password: str,
) -> dict[str, Any]:
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        return _inspect_review_queue_in_connection(
            connection, plan_id, expected_fingerprint
        )


def _insert_review_audit(
    connection: Connection[Any],
    *,
    target: dict[str, Any],
    plan: dict[str, Any],
    decision: str,
    actor: str,
    reason: str,
    evidence_sha256: str,
    before_data: dict[str, Any],
    after_data: dict[str, Any],
) -> None:
    event_id = uuid.uuid4()
    correlation_id = uuid.uuid4()
    occurred_at = datetime.now(UTC)
    event_type = (
        "catalog_identity.approved"
        if decision == "approve"
        else "catalog_identity.rejected"
    )
    evidence = {
        "import_batch_id": plan["import_batch_id"],
        "import_plan_id": plan["import_plan_id"],
        "staging_row_id": target["staging_row_id"],
        "event_type": event_type,
        "entity_type": target["identity_type"],
        "entity_id": target["public_id"],
        "occurred_at": occurred_at,
        "actor_type": "human",
        "actor_id": actor,
        "before_data": before_data,
        "after_data": after_data,
        "reason": reason,
        "correlation_id": correlation_id,
    }
    connection.execute(
        """
        INSERT INTO perfect_catalog.audit_event (
            audit_event_id, import_batch_id, import_plan_id, staging_row_id,
            event_type, entity_type, entity_id, occurred_at, actor_type,
            actor_id, before_data, after_data, reason, correlation_id,
            metadata, event_sha256
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'human',%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            event_id,
            plan["import_batch_id"],
            plan["import_plan_id"],
            target["staging_row_id"],
            event_type,
            target["identity_type"],
            target["public_id"],
            occurred_at,
            actor,
            Jsonb(json_compatible(before_data)),
            Jsonb(json_compatible(after_data)),
            reason,
            correlation_id,
            Jsonb({"review_evidence_sha256": evidence_sha256}),
            canonical_sha256(evidence),
        ),
    )


def _review_product_in_connection(
    connection: Connection[Any],
    plan_id: uuid.UUID,
    target_id: uuid.UUID,
    expected_fingerprint: str,
    expected_review_sha256: str,
    decision: str,
    actor: str,
    reason: str,
) -> dict[str, Any]:
    decision = _require_decision(decision)
    actor = _require_text(actor, "actor")
    reason = _require_text(reason, "reason")
    expected_review_sha256 = _require_sha256(
        expected_review_sha256, "review_sha256"
    )
    plan = _load_applied_plan(connection, plan_id, expected_fingerprint)
    plan_items = _load_plan_items(connection, plan_id)
    _assert_target_belongs_to_plan(target_id, plan_items)
    target = _load_review_target(connection, target_id, lock=True)
    reference = target["reference"]
    desired_catalog = "active" if decision == "approve" else "inactive"
    desired_reference = "approved" if decision == "approve" else "rejected"
    if (
        target["catalog_status"] == desired_catalog
        and reference["review_status"] == desired_reference
    ):
        event_type = (
            "catalog_identity.approved"
            if decision == "approve"
            else "catalog_identity.rejected"
        )
        audit_rows = connection.execute(
            """
            SELECT metadata->>'review_evidence_sha256'
            FROM perfect_catalog.audit_event
            WHERE import_plan_id=%s AND entity_type=%s AND entity_id=%s
              AND event_type=%s
            ORDER BY occurred_at, audit_event_id
            """,
            (
                plan_id,
                target["identity_type"],
                target["public_id"],
                event_type,
            ),
        ).fetchall()
        if len(audit_rows) != 1 or audit_rows[0][0] != expected_review_sha256:
            raise PermissionError(
                "La decision existente no coincide con el review_sha256 auditado."
            )
        return {
            "plan_id": str(plan_id),
            "product_id": str(target_id),
            "status": f"already_{desired_reference}",
            "catalog_status": desired_catalog,
            "reference_status": desired_reference,
            "review_evidence_sha256": expected_review_sha256,
        }
    if target["catalog_status"] != "pending_review" or reference[
        "review_status"
    ] not in (None, "pending"):
        raise PermissionError(
            "La identidad o su referencia ya tienen una decisión diferente; "
            "no se sobrescribe una revisión previa."
        )
    if (
        decision == "approve"
        and target["identity_type"] == "product_variant"
        and target["template_status"] != "active"
    ):
        raise PermissionError("La variante no puede aprobarse antes que su template.")
    recalculated = review_evidence_sha256(target, plan)
    if recalculated != expected_review_sha256:
        raise PermissionError(
            "El review_sha256 proporcionado no corresponde a la identidad exacta."
        )

    now = datetime.now(UTC)
    id_column = (
        "product_template_id"
        if target["identity_type"] == "product_template"
        else "product_variant_id"
    )
    changed = connection.execute(
        f"""
        UPDATE perfect_catalog.{target['identity_type']}
        SET catalog_status=%s, updated_at=%s
        WHERE {id_column}=%s AND catalog_status='pending_review'
        """,
        (desired_catalog, now, target_id),
    ).rowcount
    if changed != 1:
        raise RuntimeError("La identidad cambió mientras se revisaba.")
    changed = connection.execute(
        """
        UPDATE perfect_catalog.product_reference
        SET review_status=%s, reviewed_by=%s, reviewed_at=%s,
            review_note=%s, updated_at=%s
        WHERE product_reference_id=%s
          AND COALESCE(review_status, 'pending')='pending'
        """,
        (
            desired_reference,
            actor,
            now,
            reason,
            now,
            reference["product_reference_id"],
        ),
    ).rowcount
    if changed != 1:
        raise RuntimeError("La referencia cambió mientras se revisaba.")
    before_data = {
        "catalog_status": "pending_review",
        "reference_status": reference["review_status"],
    }
    after_data = {
        "catalog_status": desired_catalog,
        "reference_status": desired_reference,
        "product_reference_id": reference["product_reference_id"],
        "review_evidence_sha256": recalculated,
    }
    _insert_review_audit(
        connection,
        target=target,
        plan=plan,
        decision=decision,
        actor=actor,
        reason=reason,
        evidence_sha256=recalculated,
        before_data=before_data,
        after_data=after_data,
    )
    return {
        "plan_id": str(plan_id),
        "product_id": str(target_id),
        "identity_type": target["identity_type"],
        "status": desired_reference,
        "catalog_status": desired_catalog,
        "reference_status": desired_reference,
        "review_evidence_sha256": recalculated,
        "reviewed_by": actor,
    }


def review_product(
    plan_id: uuid.UUID,
    target_id: uuid.UUID,
    expected_fingerprint: str,
    expected_review_sha256: str,
    decision: str,
    actor: str,
    reason: str,
    config: DatabaseConfig,
    password: str,
) -> dict[str, Any]:
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        return _review_product_in_connection(
            connection,
            plan_id,
            target_id,
            expected_fingerprint,
            expected_review_sha256,
            decision,
            actor,
            reason,
        )


class DatabaseReviewGateway:
    """Small web-facing adapter that never exposes or persists DB credentials."""

    def __init__(self, config: DatabaseConfig, password: str) -> None:
        self._config = config
        self._password = password

    def close(self) -> None:
        self._password = ""

    def plans(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return list_review_plans(self._config, self._password, limit=limit)

    def plan(self, plan_id: uuid.UUID) -> dict[str, Any] | None:
        return get_review_plan(plan_id, self._config, self._password)

    def page(
        self,
        plan_id: uuid.UUID,
        fingerprint: str,
        *,
        query: str = "",
        state: str = "all",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        return inspect_review_queue_page(
            plan_id,
            fingerprint,
            self._config,
            self._password,
            query=query,
            state=state,
            limit=limit,
            offset=offset,
        )

    def decide(
        self,
        plan_id: uuid.UUID,
        product_id: uuid.UUID,
        fingerprint: str,
        review_sha256: str,
        decision: str,
        actor: str,
        reason: str,
    ) -> dict[str, Any]:
        return review_product(
            plan_id,
            product_id,
            fingerprint,
            review_sha256,
            decision,
            actor,
            reason,
            self._config,
            self._password,
        )
