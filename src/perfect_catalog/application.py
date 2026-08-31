from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from tools.odoo_profiler import sha256_file

from .canonical import canonical_sha256, json_compatible, normalize_name, normalize_reference
from .config import DatabaseConfig
from .importer import (
    CONTRACT_VERSION,
    NAMESPACE,
    RULES_VERSION,
    SUPPORTED_RULES_VERSIONS,
    approval_fingerprint,
    plan_hash,
    plan_item_hash,
)


APPLICABLE_OPERATIONS = frozenset({"create", "no_change", "inventory_snapshot", "media_pending"})


def _require_text(value: str, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} no puede estar vacío.")
    return text


def _require_fingerprint(value: str) -> str:
    fingerprint = str(value or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise ValueError("El fingerprint debe contener exactamente 64 caracteres hexadecimales.")
    return fingerprint


def _load_plan(connection: Connection[Any], plan_id: uuid.UUID, *, lock: bool) -> dict[str, Any]:
    suffix = " FOR UPDATE OF p" if lock else ""
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            f"""
            SELECT p.import_plan_id, p.import_batch_id, p.import_file_id,
                   p.file_sha256, p.contract_version, p.rules_version,
                   p.plan_status, p.plan_sha256, p.approval_fingerprint_sha256,
                   p.generated_at, p.approved_at, p.approved_by, p.applied_at, p.applied_by,
                   p.company_id, p.brand_profile_id, bp.code AS brand_profile_code,
                   bp.display_name AS brand_profile_name,
                   f.sha256 AS registered_file_sha256, f.storage_uri,
                   b.source_system_id
            FROM perfect_catalog.import_plan AS p
            JOIN perfect_catalog.import_file AS f
              ON f.import_file_id = p.import_file_id
             AND f.import_batch_id = p.import_batch_id
            JOIN perfect_catalog.import_batch AS b
              ON b.import_batch_id = p.import_batch_id
            LEFT JOIN perfect_catalog.brand_profile AS bp
              ON bp.brand_profile_id = p.brand_profile_id
            WHERE p.import_plan_id = %s{suffix}
            """,
            (plan_id,),
        )
        row = cursor.fetchone()
    if row is None:
        raise ValueError(f"No existe el plan {plan_id}.")
    return dict(row)


def _load_plan_items(connection: Connection[Any], plan_id: uuid.UUID) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT import_plan_item_id, import_plan_id, import_file_id, item_order,
                   staging_row_id, resolved_product_template_id, resolved_product_variant_id,
                   planned_product_template_id, planned_product_variant_id, operation_type,
                   before_values, proposed_values, issues, requires_review, item_sha256
            FROM perfect_catalog.import_plan_item
            WHERE import_plan_id = %s
            ORDER BY item_order
            """,
            (plan_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def verify_plan_integrity(
    plan: dict[str, Any],
    items: list[dict[str, Any]],
    expected_fingerprint: str,
    *,
    require_current_versions: bool = True,
) -> None:
    supplied = _require_fingerprint(expected_fingerprint)
    if not items:
        raise RuntimeError("El plan no contiene items y no puede aprobarse ni aplicarse.")
    if plan["file_sha256"] != plan["registered_file_sha256"]:
        raise RuntimeError("El hash del plan no coincide con el hash registrado del archivo.")
    for item in items:
        recalculated = plan_item_hash(item)
        if recalculated != item["item_sha256"]:
            raise RuntimeError(
                f"El item {item['import_plan_item_id']} no coincide con su hash persistido."
            )
    recalculated_plan = plan_hash(
        plan["file_sha256"],
        items,
        contract_version=plan["contract_version"],
        rules_version=plan["rules_version"],
    )
    if recalculated_plan != plan["plan_sha256"]:
        raise RuntimeError("El contenido persistido no coincide con plan_sha256.")
    recalculated_fingerprint = approval_fingerprint(
        plan["file_sha256"],
        recalculated_plan,
        contract_version=plan["contract_version"],
        rules_version=plan["rules_version"],
    )
    if recalculated_fingerprint != plan["approval_fingerprint_sha256"]:
        raise RuntimeError("El fingerprint persistido no coincide con el plan recalculado.")
    if supplied != recalculated_fingerprint:
        raise PermissionError("El fingerprint proporcionado no corresponde al plan exacto.")
    if require_current_versions and (
        plan["contract_version"] != CONTRACT_VERSION
        or plan["rules_version"] not in SUPPORTED_RULES_VERSIONS
    ):
        raise RuntimeError(
            "Las versiones del plan no coinciden con el código actual; genere y revise un plan nuevo."
        )


def assert_applicable_items(items: list[dict[str, Any]]) -> None:
    unsupported = sorted({item["operation_type"] for item in items} - APPLICABLE_OPERATIONS)
    if unsupported:
        raise NotImplementedError(
            "El apply seguro de esta etapa no admite operaciones: " + ", ".join(unsupported)
        )
    create_targets = [
        item["planned_product_template_id"]
        for item in items
        if item["operation_type"] == "create"
    ]
    if len(create_targets) != len(set(create_targets)):
        raise RuntimeError("El plan intenta crear el mismo producto más de una vez.")
    created = set(create_targets)
    orphan_snapshots = [
        item["import_plan_item_id"]
        for item in items
        if item["operation_type"] == "inventory_snapshot"
        and item["planned_product_template_id"] not in created
    ]
    if orphan_snapshots:
        raise RuntimeError(
            "Esta etapa solo admite snapshots de productos creados por el mismo plan."
        )


def _verify_source_file(plan: dict[str, Any], source_root: Path) -> Path:
    stored = Path(str(plan["storage_uri"]))
    source = stored if stored.is_absolute() else source_root.resolve() / stored
    source = source.resolve(strict=True)
    if sha256_file(source) != plan["file_sha256"]:
        raise RuntimeError("El archivo físico ya no coincide con el hash aprobado.")
    return source


def _insert_audit_event(
    connection: Connection[Any],
    *,
    plan: dict[str, Any],
    event_type: str,
    entity_type: str,
    entity_id: uuid.UUID,
    actor: str,
    reason: str,
    after_data: dict[str, Any],
    before_data: dict[str, Any] | None = None,
    staging_row_id: uuid.UUID | None = None,
    correlation_id: uuid.UUID | None = None,
) -> uuid.UUID:
    event_id = uuid.uuid4()
    occurred_at = datetime.now(UTC)
    evidence = {
        "import_batch_id": plan["import_batch_id"],
        "import_plan_id": plan["import_plan_id"],
        "staging_row_id": staging_row_id,
        "event_type": event_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
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
            event_type, entity_type, entity_id, occurred_at, actor_type, actor_id,
            before_data, after_data, reason, correlation_id, event_sha256
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'human',%s,%s,%s,%s,%s,%s)
        """,
        (
            event_id,
            plan["import_batch_id"],
            plan["import_plan_id"],
            staging_row_id,
            event_type,
            entity_type,
            entity_id,
            occurred_at,
            actor,
            Jsonb(json_compatible(before_data)) if before_data is not None else None,
            Jsonb(json_compatible(after_data)),
            reason,
            correlation_id,
            canonical_sha256(evidence),
        ),
    )
    return event_id


def _approve_plan_in_connection(
    connection: Connection[Any],
    plan_id: uuid.UUID,
    expected_fingerprint: str,
    actor: str,
    reason: str,
    *,
    verify_source: bool = True,
    source_root: Path = Path.cwd(),
) -> dict[str, Any]:
    actor = _require_text(actor, "actor")
    reason = _require_text(reason, "reason")
    plan = _load_plan(connection, plan_id, lock=True)
    items = _load_plan_items(connection, plan_id)
    if plan["plan_status"] != "awaiting_review":
        raise PermissionError(
            f"Aprobación rechazada: el plan está en {plan['plan_status']!r}."
        )
    verify_plan_integrity(plan, items, expected_fingerprint)
    assert_applicable_items(items)
    if verify_source:
        _verify_source_file(plan, source_root)
    now = datetime.now(UTC)
    changed = connection.execute(
        """
        UPDATE perfect_catalog.import_plan
        SET plan_status='approved', approved_at=%s, approved_by=%s
        WHERE import_plan_id=%s AND plan_status='awaiting_review'
        """,
        (now, actor, plan_id),
    ).rowcount
    if changed != 1:
        raise RuntimeError("El plan cambió de estado mientras se aprobaba.")
    connection.execute(
        "UPDATE perfect_catalog.import_batch SET status='ready', approved_by=%s WHERE import_batch_id=%s",
        (actor, plan["import_batch_id"]),
    )
    plan["plan_status"] = "approved"
    _insert_audit_event(
        connection,
        plan=plan,
        event_type="import_plan.approved",
        entity_type="import_plan",
        entity_id=plan_id,
        actor=actor,
        reason=reason,
        before_data={"plan_status": "awaiting_review"},
        after_data={"plan_status": "approved", "fingerprint": expected_fingerprint},
    )
    return {"plan_id": str(plan_id), "status": "approved", "approved_by": actor}


def approve_plan(
    plan_id: uuid.UUID,
    expected_fingerprint: str,
    actor: str,
    reason: str,
    config: DatabaseConfig,
    password: str,
) -> dict[str, Any]:
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        return _approve_plan_in_connection(
            connection, plan_id, expected_fingerprint, actor, reason
        )


def _ensure_brand(
    connection: Connection[Any], source_system_id: uuid.UUID, brand_profile_id: uuid.UUID,
    brand_code: str, brand_name: str,
) -> uuid.UUID:
    normalized = normalize_name(brand_name)
    code = brand_code
    brand_id = uuid.uuid5(NAMESPACE, f"brand:{normalized}")
    company_row = connection.execute(
        "SELECT company_id FROM perfect_catalog.brand_profile WHERE brand_profile_id=%s",
        (brand_profile_id,),
    ).fetchone()
    if company_row is None:
        raise RuntimeError("El perfil de marca no pertenece a una Company válida.")
    company_id = company_row[0]
    connection.execute(
        """
        INSERT INTO perfect_catalog.brand (
            brand_id, source_system_id, brand_profile_id, company_id, code, name, normalized_name
        ) VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT DO NOTHING
        """,
        (brand_id, source_system_id, brand_profile_id, company_id, code, brand_name, normalized),
    )
    row = connection.execute(
        "SELECT brand_id, source_system_id, normalized_name, brand_profile_id FROM perfect_catalog.brand WHERE code=%s",
        (code,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"No se pudo resolver la marca {code!r} después del insert idempotente.")
    if row[1] != source_system_id or row[2] != normalized or row[3] != brand_profile_id:
        raise RuntimeError(
            f"La marca existente con código {code!r} no coincide con la fuente y nombre del plan."
        )
    return row[0]


def _ensure_category(
    connection: Connection[Any], source_system_id: uuid.UUID, source_path: Any
) -> uuid.UUID | None:
    path = str(source_path or "").strip()
    if not path:
        return None
    row = connection.execute(
        """
        SELECT product_category_id
        FROM perfect_catalog.product_category
        WHERE source_system_id=%s AND source_path=%s
        ORDER BY product_category_id
        LIMIT 1
        """,
        (source_system_id, path),
    ).fetchone()
    if row:
        return row[0]
    category_id = uuid.uuid5(NAMESPACE, f"category:{source_system_id}:{normalize_name(path)}")
    name = path.rsplit("/", 1)[-1].strip() or path
    connection.execute(
        """
        INSERT INTO perfect_catalog.product_category (
            product_category_id, source_system_id, name, normalized_name, source_path
        ) VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT (product_category_id) DO NOTHING
        """,
        (category_id, source_system_id, name, normalize_name(name), path),
    )
    persisted = connection.execute(
        """
        SELECT source_system_id, source_path
        FROM perfect_catalog.product_category
        WHERE product_category_id=%s
        """,
        (category_id,),
    ).fetchone()
    if persisted is None or persisted[0] != source_system_id or persisted[1] != path:
        raise RuntimeError("La categoría determinista colisionó con datos incompatibles.")
    return category_id


def _ensure_vehicle_make(connection: Connection[Any], name: str) -> uuid.UUID:
    normalized = normalize_name(name)
    existing = connection.execute(
        """SELECT vehicle_make_id FROM perfect_catalog.vehicle_make
           WHERE normalized_name=%s ORDER BY
             CASE review_status WHEN 'approved' THEN 0 WHEN 'pending' THEN 1 ELSE 2 END,
             vehicle_make_id LIMIT 1""",
        (normalized,),
    ).fetchone()
    if existing:
        return existing[0]
    make_id = uuid.uuid5(NAMESPACE, f"vehicle-make:{normalized}")
    connection.execute(
        """
        INSERT INTO perfect_catalog.vehicle_make (
            vehicle_make_id, name, normalized_name, review_status
        ) VALUES (%s,%s,%s,'pending')
        ON CONFLICT (vehicle_make_id) DO NOTHING
        """,
        (make_id, name.strip(), normalized),
    )
    return make_id


def _ensure_vehicle_model(
    connection: Connection[Any], make_id: uuid.UUID, name: str | None
) -> uuid.UUID | None:
    model = str(name or "").strip()
    if not model:
        return None
    normalized = normalize_name(model)
    existing = connection.execute(
        """SELECT vehicle_model_id FROM perfect_catalog.vehicle_model
           WHERE vehicle_make_id=%s AND normalized_name=%s ORDER BY
             CASE review_status WHEN 'approved' THEN 0 WHEN 'pending' THEN 1 ELSE 2 END,
             vehicle_model_id LIMIT 1""",
        (make_id, normalized),
    ).fetchone()
    if existing:
        return existing[0]
    model_id = uuid.uuid5(NAMESPACE, f"vehicle-model:{make_id}:{normalized}")
    connection.execute(
        """
        INSERT INTO perfect_catalog.vehicle_model (
            vehicle_model_id, vehicle_make_id, name, normalized_name, review_status
        ) VALUES (%s,%s,%s,%s,'pending')
        ON CONFLICT (vehicle_model_id) DO NOTHING
        """,
        (model_id, make_id, model, normalized),
    )
    return model_id


def _insert_vehicle_applications(
    connection: Connection[Any], plan: dict[str, Any], item: dict[str, Any]
) -> int:
    proposed = item["proposed_values"]
    enrichment = proposed.get("name_enrichment") or {}
    applications = enrichment.get("applications") or []
    inserted = 0
    for order, application in enumerate(applications, start=1):
        make_name = str(application.get("vehicle_brand") or "").strip()
        if not make_name:
            continue
        make_id = _ensure_vehicle_make(connection, make_name)
        model_id = _ensure_vehicle_model(connection, make_id, application.get("model_suggestion"))
        years = application.get("years") or {}
        positions = [str(value) for value in application.get("positions") or [] if str(value).strip()]
        engines = [str(value) for value in application.get("engines") or [] if str(value).strip()]
        candidate_id = uuid.uuid5(
            item["import_plan_item_id"], f"vehicle-application:{order}:{make_id}:{model_id}"
        )
        notes = {
            "engines": engines,
            "positions": positions,
            "parser_version": enrichment.get("parser_version"),
            "year_evidence": application.get("year_evidence"),
        }
        connection.execute(
            """
            INSERT INTO perfect_catalog.product_application_candidate (
                product_application_candidate_id, product_template_id, staging_row_id,
                vehicle_make_id, vehicle_model_id, evidence_original,
                rule_code, rule_version, confidence, review_status,
                year_from, year_to, position, notes
            ) VALUES (%s,%s,%s,%s,%s,%s,'product-name-parser',%s,%s,'pending',%s,%s,%s,%s)
            ON CONFLICT (product_application_candidate_id) DO NOTHING
            """,
            (
                candidate_id, item["planned_product_template_id"], item["staging_row_id"],
                make_id, model_id, proposed["name_original"],
                str(enrichment.get("parser_version") or "unknown"),
                application.get("confidence", 0), years.get("from"), years.get("to"),
                positions[0] if positions else None,
                json.dumps(notes, ensure_ascii=False, sort_keys=True),
            ),
        )
        inserted += 1
    return inserted


def _apply_create_item(
    connection: Connection[Any],
    plan: dict[str, Any],
    item: dict[str, Any],
    brand_id: uuid.UUID,
    actor: str,
    reason: str,
    correlation_id: uuid.UUID,
) -> None:
    proposed = item["proposed_values"]
    product_id = item["planned_product_template_id"]
    category_id = _ensure_category(
        connection, plan["source_system_id"], proposed.get("category_path")
    )
    connection.execute(
        """
        INSERT INTO perfect_catalog.product_template (
            product_template_id, source_system_id, brand_id, product_category_id,
            name_original, name_normalized, currency_code, uom_original,
            activity_state, is_favorite, show_quantity_status, source_active,
            catalog_status, variant_count_observed, source_updated_at,
            created_from_staging_row_id, last_confirmed_batch_id
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            product_id,
            plan["source_system_id"],
            brand_id,
            category_id,
            proposed["name_original"],
            normalize_name(proposed["name_original"]),
            proposed.get("currency"),
            proposed.get("uom_original"),
            proposed.get("activity_state"),
            proposed.get("is_favorite"),
            proposed.get("show_quantity_status"),
            proposed.get("source_active"),
            proposed.get("catalog_status", "pending_review"),
            proposed.get("variant_count_observed"),
            proposed.get("source_updated_at"),
            item["staging_row_id"],
            plan["import_batch_id"],
        ),
    )
    _insert_vehicle_applications(connection, plan, item)
    reference = str(proposed["internal_reference_original"])
    normalized_reference = normalize_reference(reference)
    reference_id = uuid.uuid5(
        NAMESPACE, f"reference:{product_id}:internal:{normalized_reference}"
    )
    connection.execute(
        """
        INSERT INTO perfect_catalog.product_reference (
            product_reference_id, source_system_id, brand_id, product_template_id,
            staging_row_id, reference_type, value_original, value_normalized,
            is_primary, review_status
        ) VALUES (%s,%s,%s,%s,%s,'internal',%s,%s,true,'pending')
        """,
        (
            reference_id,
            plan["source_system_id"],
            brand_id,
            product_id,
            item["staging_row_id"],
            reference,
            normalized_reference,
        ),
    )
    _insert_audit_event(
        connection,
        plan=plan,
        event_type="product_template.created",
        entity_type="product_template",
        entity_id=product_id,
        actor=actor,
        reason=reason,
        staging_row_id=item["staging_row_id"],
        after_data={"product_template_id": product_id, **proposed},
        correlation_id=correlation_id,
    )


def _apply_snapshot_item(
    connection: Connection[Any],
    plan: dict[str, Any],
    item: dict[str, Any],
    actor: str,
    reason: str,
    correlation_id: uuid.UUID,
) -> None:
    proposed = item["proposed_values"]
    snapshot_id = uuid.uuid5(item["import_plan_item_id"], "inventory-snapshot")
    connection.execute(
        """
        INSERT INTO perfect_catalog.inventory_snapshot (
            inventory_snapshot_id, product_template_id, product_variant_id,
            import_batch_id, import_plan_id, import_plan_item_id,
            import_file_id, staging_row_id, quantity_on_hand, quantity_available,
            uom_original, captured_at, source_updated_at, source_date_serial, metadata
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            snapshot_id,
            item["planned_product_template_id"],
            item["planned_product_variant_id"],
            plan["import_batch_id"],
            plan["import_plan_id"],
            item["import_plan_item_id"],
            plan["import_file_id"],
            item["staging_row_id"],
            proposed["quantity_on_hand"],
            proposed["quantity_available"],
            proposed["uom_original"],
            plan["generated_at"],
            proposed.get("source_updated_at"),
            proposed.get("source_date_serial"),
            Jsonb({"source": "approved_import_plan"}),
        ),
    )
    _insert_audit_event(
        connection,
        plan=plan,
        event_type="inventory_snapshot.created",
        entity_type="inventory_snapshot",
        entity_id=snapshot_id,
        actor=actor,
        reason=reason,
        staging_row_id=item["staging_row_id"],
        after_data={"inventory_snapshot_id": snapshot_id, **proposed},
        correlation_id=correlation_id,
    )


def _apply_plan_in_connection(
    connection: Connection[Any],
    plan_id: uuid.UUID,
    expected_fingerprint: str,
    actor: str,
    reason: str,
    *,
    verify_source: bool = True,
    source_root: Path = Path.cwd(),
) -> dict[str, Any]:
    actor = _require_text(actor, "actor")
    reason = _require_text(reason, "reason")
    plan = _load_plan(connection, plan_id, lock=True)
    items = _load_plan_items(connection, plan_id)
    if plan["plan_status"] == "applied":
        verify_plan_integrity(plan, items, expected_fingerprint)
        return {
            "plan_id": str(plan_id),
            "status": "already_applied",
            "applied_by": plan["applied_by"],
        }
    if plan["plan_status"] != "approved":
        raise PermissionError(f"Apply rechazado: el plan está en {plan['plan_status']!r}.")
    verify_plan_integrity(plan, items, expected_fingerprint)
    assert_applicable_items(items)
    if verify_source:
        _verify_source_file(plan, source_root)
    changed = connection.execute(
        "UPDATE perfect_catalog.import_plan SET plan_status='applying' WHERE import_plan_id=%s AND plan_status='approved'",
        (plan_id,),
    ).rowcount
    if changed != 1:
        raise RuntimeError("No se pudo adquirir la aplicación única del plan.")
    connection.execute(
        "UPDATE perfect_catalog.import_batch SET status='applying' WHERE import_batch_id=%s",
        (plan["import_batch_id"],),
    )
    plan["plan_status"] = "applying"
    correlation_id = uuid.uuid4()
    creates_products = any(item["operation_type"] == "create" for item in items)
    if creates_products and not plan.get("brand_profile_id"):
        raise RuntimeError("Selecciona un perfil de marca antes de aplicar el plan.")
    brand_id = (
        _ensure_brand(
            connection, plan["source_system_id"], plan["brand_profile_id"],
            plan["brand_profile_code"], plan["brand_profile_name"],
        ) if creates_products else None
    )
    counts = {"create": 0, "inventory_snapshot": 0, "media_pending": 0, "no_change": 0}
    for item in items:
        operation = item["operation_type"]
        if operation == "create":
            if brand_id is None:  # Defensive: assert_applicable_items already classified the plan.
                raise RuntimeError("No se pudo resolver la marca para el alta planificada.")
            _apply_create_item(connection, plan, item, brand_id, actor, reason, correlation_id)
        elif operation == "inventory_snapshot":
            _apply_snapshot_item(connection, plan, item, actor, reason, correlation_id)
        counts[operation] += 1
    warning_count = int(connection.execute(
        "SELECT count(*) FROM perfect_catalog.import_issue WHERE import_batch_id=%s AND status='open' AND severity IN ('info','warning')",
        (plan["import_batch_id"],),
    ).fetchone()[0])
    completed_status = "completed_with_warnings" if warning_count else "completed"
    now = datetime.now(UTC)
    connection.execute(
        """
        UPDATE perfect_catalog.import_plan
        SET plan_status='applied', applied_at=%s, applied_by=%s
        WHERE import_plan_id=%s AND plan_status='applying'
        """,
        (now, actor, plan_id),
    )
    connection.execute(
        """
        UPDATE perfect_catalog.import_batch
        SET status=%s, finished_at=%s,
            statistics=COALESCE(statistics, '{}'::jsonb) || %s
        WHERE import_batch_id=%s
        """,
        (completed_status, now, Jsonb({"apply": counts}), plan["import_batch_id"]),
    )
    plan["plan_status"] = "applied"
    _insert_audit_event(
        connection,
        plan=plan,
        event_type="import_plan.applied",
        entity_type="import_plan",
        entity_id=plan_id,
        actor=actor,
        reason=reason,
        before_data={"plan_status": "applying"},
        after_data={"plan_status": "applied", "counts": counts},
        correlation_id=correlation_id,
    )
    return {"plan_id": str(plan_id), "status": "applied", "counts": counts}


def apply_approved_plan(
    plan_id: uuid.UUID,
    expected_fingerprint: str,
    actor: str,
    reason: str,
    config: DatabaseConfig,
    password: str,
) -> dict[str, Any]:
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        return _apply_plan_in_connection(
            connection, plan_id, expected_fingerprint, actor, reason
        )


def approve_and_apply_plan(
    plan_id: uuid.UUID, expected_fingerprint: str, actor: str, reason: str,
    config: DatabaseConfig, password: str, *, brand_code: str,
) -> dict[str, Any]:
    """Una confirmación del operador; dos eventos auditados en una transacción."""
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        plan = _load_plan(connection, plan_id, lock=True)
        if plan["plan_status"] != "awaiting_review":
            raise PermissionError("La marca solo puede elegirse antes de aprobar el plan.")
        if plan["company_id"] is None:
            raise PermissionError("El plan histórico no tiene Company verificable.")
        profile = connection.execute(
            """SELECT brand_profile_id, code, display_name
               FROM perfect_catalog.brand_profile
               WHERE code=%s AND company_id=%s""",
            (str(brand_code or "").strip().upper(), plan["company_id"]),
        ).fetchone()
        if profile is None:
            raise ValueError("El perfil de marca seleccionado no existe.")
        connection.execute(
            "UPDATE perfect_catalog.import_plan SET brand_profile_id=%s WHERE import_plan_id=%s AND plan_status='awaiting_review'",
            (profile[0], plan_id),
        )
        _insert_audit_event(
            connection, plan=plan, event_type="import_plan.brand_selected",
            entity_type="import_plan", entity_id=plan_id, actor=actor, reason=reason,
            before_data={"brand_profile_id": str(plan["brand_profile_id"]) if plan["brand_profile_id"] else None},
            after_data={"brand_profile_id": str(profile[0]), "brand_code": profile[1]},
        )
        _approve_plan_in_connection(
            connection, plan_id, expected_fingerprint, actor, reason
        )
        result = _apply_plan_in_connection(
            connection, plan_id, expected_fingerprint, actor, reason,
            verify_source=False,
        )
        result["status"] = "prepared"
        return result
