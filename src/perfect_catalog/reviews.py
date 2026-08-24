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
    plan = _load_applied_plan(
        connection, plan_id, expected_fingerprint, lock=False
    )
    plan_items = _load_plan_items(connection, plan_id)
    target_ids = sorted(
        {
            item.get("planned_product_variant_id")
            or item["planned_product_template_id"]
            for item in plan_items
            if item["operation_type"] == "create"
        },
        key=str,
    )
    if not target_ids:
        raise RuntimeError("El plan aplicado no creó identidades revisables.")
    if len(target_ids) > MAX_REVIEW_QUEUE_ITEMS:
        raise RuntimeError(
            "La cola supera el limite seguro de 5000 identidades del piloto; "
            "requiere inspeccion paginada antes de continuar."
        )
    candidates = []
    for target_id in target_ids:
        target = _load_review_target(connection, target_id, lock=False)
        evidence = review_evidence(target, plan)
        candidates.append(
            {
                "product_id": str(target_id),
                "identity_type": target["identity_type"],
                "name": target["name_original"],
                "variant_name": target["variant_name"],
                "reference": target["reference"]["value_original"],
                "catalog_status": target["catalog_status"],
                "reference_status": target["reference"]["review_status"],
                "source_row_number": target["source_row_number"],
                "review_sha256": canonical_sha256(evidence),
            }
        )
    queue_evidence = {
        "algorithm": REVIEW_ALGORITHM,
        "source_plan_id": plan_id,
        "source_plan_fingerprint_sha256": plan["approval_fingerprint_sha256"],
        "items": [
            {"product_id": item["product_id"], "review_sha256": item["review_sha256"]}
            for item in candidates
        ],
    }
    return {
        "plan_id": str(plan_id),
        "plan_status": plan["plan_status"],
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
