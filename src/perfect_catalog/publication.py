from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .application import _load_plan, _load_plan_items, verify_plan_integrity
from .canonical import canonical_sha256, json_compatible, normalize_name
from .config import DatabaseConfig
from .importer import BRAND, NAMESPACE
from .releases import (
    RELEASE_HASH_ALGORITHM,
    SNAPSHOT_SCHEMA_VERSION,
    product_snapshot_sha256,
    release_snapshot_sha256,
    validate_release_definition,
    validate_release_items,
)


RELEASE_NAMESPACE = uuid.uuid5(NAMESPACE, "catalog-release")
VERSION_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def _require_text(value: str, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} no puede estar vacío.")
    return text


def _require_version(value: str) -> str:
    version = _require_text(value, "version")
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(
            "version debe tener 1-80 caracteres alfanuméricos y solo '.', '_' o '-'."
        )
    return version


def _require_sha256(value: str, label: str = "snapshot_sha256") -> str:
    digest = str(value or "").strip().lower()
    if not SHA256_PATTERN.fullmatch(digest):
        raise ValueError(f"{label} debe contener 64 caracteres hexadecimales.")
    return digest


def snapshot_from_record(record: dict[str, Any]) -> dict[str, Any]:
    template_name = _require_text(record["name_original"], "name_original")
    variant_name = str(record.get("variant_name") or "").strip()
    display_name = (
        f"{template_name} — {variant_name}" if variant_name else template_name
    )
    application_details = list(record.get("application_details") or [])
    for item in application_details:
        notes = item.get("notes")
        if isinstance(notes, str):
            try:
                parsed_notes = json.loads(notes)
            except json.JSONDecodeError:
                parsed_notes = {}
            if isinstance(parsed_notes, dict):
                item["engines"] = list(parsed_notes.get("engines") or [])
                item["positions"] = list(parsed_notes.get("positions") or [])
    vehicle_makes = sorted({
        str(item.get("make") or "").strip()
        for item in application_details if str(item.get("make") or "").strip()
    })
    applications: list[str] = []
    for item in application_details:
        label = " ".join(filter(None, (
            str(item.get("make") or "").strip(), str(item.get("model") or "").strip()
        )))
        year_from, year_to = item.get("year_from"), item.get("year_to")
        if year_from:
            label += f" {year_from}" + (f"–{year_to}" if year_to else "+")
        if item.get("position"):
            label += f" · {item['position']}"
        if item.get("engines"):
            label += " · " + ", ".join(map(str, item["engines"]))
        if label.strip() and label.strip() not in applications:
            applications.append(label.strip())
    return {
        "product_template_id": str(record["product_template_id"]),
        "product_variant_id": (
            str(record["product_variant_id"])
            if record.get("product_variant_id") is not None
            else None
        ),
        "source_row_number": record.get("source_row_number"),
        "source_import_batch_id": (
            str(record["source_import_batch_id"])
            if record.get("source_import_batch_id") is not None
            else None
        ),
        "internal_reference_original": _require_text(
            record["reference_original"], "internal_reference_original"
        ),
        "internal_reference_normalized": _require_text(
            record["reference_normalized"], "internal_reference_normalized"
        ),
        "name_original": display_name,
        "name_normalized": normalize_name(display_name),
        "template_name_original": template_name,
        "variant_name": variant_name or None,
        "category_path": record.get("category_path"),
        "quantity_available": None,
        "uom_original": None,
        "currency": None,
        "image_status": "present" if record.get("has_processed_media") or record.get("approved_image_relpath") else "absent",
        "image_storage_relpath": record.get("approved_image_relpath"),
        "image_sha256": record.get("approved_image_sha256"),
        "image_media_type": record.get("approved_image_media_type"),
        "brand": _require_text(record["brand_name"], "brand"),
        "vehicle_makes": vehicle_makes,
        "vehicle_make": vehicle_makes[0] if len(vehicle_makes) == 1 else None,
        "applications": applications,
        "application_details": application_details,
        "family": None,
        "source_active": record.get("source_active"),
        "source_updated_at": json_compatible(record.get("source_updated_at")),
        "catalog_status": "active",
    }


def _load_applied_plan(
    connection: Connection[Any],
    plan_id: uuid.UUID,
    expected_fingerprint: str,
    *,
    lock: bool = True,
) -> dict[str, Any]:
    plan = _load_plan(connection, plan_id, lock=lock)
    items = _load_plan_items(connection, plan_id)
    verify_plan_integrity(plan, items, expected_fingerprint)
    if plan["plan_status"] != "applied":
        raise PermissionError(
            f"El release requiere un plan aplicado; {plan_id} está en {plan['plan_status']!r}."
        )
    return plan


def _resolve_brand(
    connection: Connection[Any], source_system_id: uuid.UUID, brand_name: str
) -> dict[str, Any]:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT brand_id, name, normalized_name
            FROM perfect_catalog.brand
            WHERE source_system_id=%s AND normalized_name=%s
            ORDER BY brand_id
            """,
            (source_system_id, normalize_name(brand_name)),
        )
        rows = [dict(row) for row in cursor.fetchall()]
    if len(rows) != 1:
        raise RuntimeError(
            f"Se esperaba exactamente una marca {brand_name!r} para la fuente del plan; "
            f"se encontraron {len(rows)}."
        )
    return rows[0]


def _load_release_records(
    connection: Connection[Any], brand_id: uuid.UUID
) -> list[dict[str, Any]]:
    pending_count = connection.execute(
        """
        SELECT
            (SELECT count(*) FROM perfect_catalog.product_template
             WHERE brand_id=%s AND catalog_status='pending_review')
          + (SELECT count(*)
             FROM perfect_catalog.product_variant AS v
             JOIN perfect_catalog.product_template AS p
               ON p.product_template_id=v.product_template_id
             WHERE p.brand_id=%s AND p.catalog_status='active'
               AND v.catalog_status='pending_review')
        """,
        (brand_id, brand_id),
    ).fetchone()[0]
    if pending_count:
        raise RuntimeError(
            f"La marca conserva {pending_count} identidades pendientes de revisión."
        )

    inactive_variant_templates = connection.execute(
        """
        SELECT count(*)
        FROM perfect_catalog.product_template AS p
        WHERE p.brand_id=%s AND p.catalog_status='active'
          AND EXISTS (
              SELECT 1 FROM perfect_catalog.product_variant AS any_v
              WHERE any_v.product_template_id=p.product_template_id
          )
          AND NOT EXISTS (
              SELECT 1 FROM perfect_catalog.product_variant AS active_v
              WHERE active_v.product_template_id=p.product_template_id
                AND active_v.catalog_status='active'
          )
        """,
        (brand_id,),
    ).fetchone()[0]
    if inactive_variant_templates:
        raise RuntimeError(
            "Hay productos activos con variantes, pero sin una variante activa publicable."
        )

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            WITH targets AS (
                SELECT p.product_template_id, v.product_variant_id,
                       p.name_original, v.variant_name, p.currency_code,
                       p.uom_original, p.source_active, p.source_updated_at,
                       p.product_category_id, p.created_from_staging_row_id,
                       v.created_from_staging_row_id AS variant_staging_row_id,
                       p.last_confirmed_batch_id
                FROM perfect_catalog.product_template AS p
                LEFT JOIN perfect_catalog.product_variant AS v
                  ON v.product_template_id=p.product_template_id
                 AND v.catalog_status='active'
                WHERE p.brand_id=%s AND p.catalog_status='active'
                  AND (
                      v.product_variant_id IS NOT NULL
                      OR NOT EXISTS (
                          SELECT 1 FROM perfect_catalog.product_variant AS any_v
                          WHERE any_v.product_template_id=p.product_template_id
                      )
                  )
            )
            SELECT t.product_template_id, t.product_variant_id,
                   t.name_original, t.variant_name, t.currency_code,
                   COALESCE(inv.uom_original, t.uom_original) AS uom_original,
                   t.source_active, t.source_updated_at, c.source_path AS category_path,
                   COALESCE(vsr.source_row_number, tsr.source_row_number) AS source_row_number,
                   ref.reference_count, ref.value_original AS reference_original,
                   ref.value_normalized AS reference_normalized,
                   inv.quantity_available,
                   COALESCE(inv.import_batch_id, t.last_confirmed_batch_id)
                       AS source_import_batch_id,
                   EXISTS (
                       SELECT 1
                       FROM perfect_catalog.product_media AS pm
                       JOIN perfect_catalog.media_asset AS ma
                         ON ma.media_asset_id=pm.media_asset_id
                       WHERE pm.product_template_id=t.product_template_id
                         AND pm.product_variant_id IS NOT DISTINCT FROM t.product_variant_id
                         AND pm.is_primary=true AND ma.status='procesada'
                   ) AS has_processed_media,
                   approved_image.storage_relpath AS approved_image_relpath,
                   approved_image.content_sha256 AS approved_image_sha256,
                   approved_image.media_type AS approved_image_media_type,
                   COALESCE(app.application_details, '[]'::jsonb) AS application_details,
                   b.name AS brand_name
            FROM targets AS t
            JOIN perfect_catalog.brand AS b ON b.brand_id=%s
            LEFT JOIN perfect_catalog.product_category AS c
              ON c.product_category_id=t.product_category_id
            JOIN perfect_catalog.staging_row AS tsr
              ON tsr.staging_row_id=t.created_from_staging_row_id
            LEFT JOIN perfect_catalog.staging_row AS vsr
              ON vsr.staging_row_id=t.variant_staging_row_id
            LEFT JOIN LATERAL (
                SELECT count(*)::int AS reference_count,
                       min(r.value_original) AS value_original,
                       min(r.value_normalized) AS value_normalized
                FROM perfect_catalog.product_reference AS r
                WHERE r.product_template_id=t.product_template_id
                  AND r.product_variant_id IS NOT DISTINCT FROM t.product_variant_id
                  AND r.reference_type='internal'
                  AND r.is_primary=true
                  AND r.review_status='approved'
            ) AS ref ON true
            LEFT JOIN LATERAL (
                SELECT i.quantity_available, i.uom_original, i.import_batch_id
                FROM perfect_catalog.inventory_snapshot AS i
                WHERE i.product_template_id=t.product_template_id
                  AND i.product_variant_id IS NOT DISTINCT FROM t.product_variant_id
                ORDER BY i.captured_at DESC, i.inventory_snapshot_id DESC
                LIMIT 1
            ) AS inv ON true
            LEFT JOIN LATERAL (
                SELECT m.storage_relpath, m.content_sha256, m.media_type
                FROM perfect_catalog.approved_image_materialization AS m
                WHERE m.product_template_id=t.product_template_id
                  AND m.product_variant_id IS NOT DISTINCT FROM t.product_variant_id
                ORDER BY m.materialized_at, m.approved_image_materialization_id
                LIMIT 1
            ) AS approved_image ON true
            LEFT JOIN LATERAL (
                SELECT jsonb_agg(jsonb_build_object(
                    'make', vm.name, 'model', vmo.name,
                    'year_from', pac.year_from, 'year_to', pac.year_to,
                    'position', pac.position, 'confidence', pac.confidence,
                    'notes', pac.notes
                ) ORDER BY vm.name, vmo.name NULLS LAST,
                           pac.product_application_candidate_id) AS application_details
                FROM perfect_catalog.product_application_candidate AS pac
                JOIN perfect_catalog.vehicle_make AS vm
                  ON vm.vehicle_make_id=pac.vehicle_make_id
                 AND vm.review_status='approved'
                LEFT JOIN perfect_catalog.vehicle_model AS vmo
                  ON vmo.vehicle_model_id=pac.vehicle_model_id
                 AND vmo.review_status='approved'
                WHERE pac.product_template_id=t.product_template_id
                  AND pac.review_status='approved'
            ) AS app ON true
            ORDER BY ref.value_normalized NULLS LAST,
                     COALESCE(t.product_variant_id, t.product_template_id)
            """,
            (brand_id, brand_id),
        )
        records = [dict(row) for row in cursor.fetchall()]

    if not records:
        raise RuntimeError("La marca no tiene productos activos publicables.")
    invalid = [
        str(record.get("product_variant_id") or record["product_template_id"])
        for record in records
        if record["reference_count"] != 1
    ]
    if invalid:
        preview = ", ".join(invalid[:5])
        raise RuntimeError(
            "Cada producto publicable requiere exactamente una referencia interna primaria "
            f"aprobada; identidades inválidas: {preview}."
        )
    return records


def _release_items(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for order, record in enumerate(records, start=1):
        snapshot = snapshot_from_record(record)
        items.append(
            {
                "item_order": order,
                "product_template_id": record["product_template_id"],
                "product_variant_id": record.get("product_variant_id"),
                "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
                "snapshot_data": snapshot,
                "snapshot_sha256": product_snapshot_sha256(snapshot),
                "section_key": record.get("category_path"),
                "grouping_keys": {
                    "category": record.get("category_path"),
                    "vehicle_makes": snapshot.get("vehicle_makes", []),
                },
                "source_import_batch_id": record.get("source_import_batch_id"),
            }
        )
    validate_release_items(items)
    return items


def _insert_release_audit(
    connection: Connection[Any],
    *,
    release: dict[str, Any],
    event_type: str,
    actor: str,
    reason: str,
    before_data: dict[str, Any] | None,
    after_data: dict[str, Any],
    correlation_id: uuid.UUID,
) -> None:
    event_id = uuid.uuid4()
    occurred_at = datetime.now(UTC)
    plan_id = uuid.UUID(str(release["definition"]["source_plan_id"]))
    batch_id = uuid.UUID(str(release["definition"]["source_import_batch_id"]))
    evidence = {
        "import_batch_id": batch_id,
        "import_plan_id": plan_id,
        "staging_row_id": None,
        "event_type": event_type,
        "entity_type": "catalog_release",
        "entity_id": release["catalog_release_id"],
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
            audit_event_id, import_batch_id, import_plan_id, event_type,
            entity_type, entity_id, occurred_at, actor_type, actor_id,
            before_data, after_data, reason, correlation_id, event_sha256
        ) VALUES (%s,%s,%s,%s,'catalog_release',%s,%s,'human',%s,%s,%s,%s,%s,%s)
        """,
        (
            event_id,
            batch_id,
            plan_id,
            event_type,
            release["catalog_release_id"],
            occurred_at,
            actor,
            Jsonb(json_compatible(before_data)) if before_data is not None else None,
            Jsonb(json_compatible(after_data)),
            reason,
            correlation_id,
            canonical_sha256(evidence),
        ),
    )


def _load_release(
    connection: Connection[Any], release_id: uuid.UUID, *, lock: bool
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    suffix = " FOR UPDATE OF r" if lock else ""
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            f"""
            SELECT r.catalog_release_id, r.brand_id, r.version, r.status,
                   r.definition, r.created_at, r.created_by, r.published_at,
                   r.published_by, r.archived_at, r.archived_by,
                   r.snapshot_sha256
            FROM perfect_catalog.catalog_release AS r
            WHERE r.catalog_release_id=%s{suffix}
            """,
            (release_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"No existe el release {release_id}.")
        release = dict(row)
        cursor.execute(
            """
            SELECT catalog_release_item_id, item_order, product_template_id,
                   product_variant_id, snapshot_schema_version, snapshot_data,
                   snapshot_sha256, section_key, grouping_keys,
                   source_import_batch_id
            FROM perfect_catalog.catalog_release_item
            WHERE catalog_release_id=%s
            ORDER BY item_order
            """,
            (release_id,),
        )
        items = [dict(item) for item in cursor.fetchall()]
    return release, items


def _verify_release(
    release: dict[str, Any], items: list[dict[str, Any]], expected_sha256: str | None = None
) -> None:
    if not items:
        raise RuntimeError("El release no contiene items.")
    definition = release["definition"]
    validate_release_definition(definition, len(items))
    validate_release_items(items)
    recalculated = release_snapshot_sha256(
        release["brand_id"], release["version"], definition, items
    )
    if recalculated != release["snapshot_sha256"]:
        raise RuntimeError("El contenido no coincide con snapshot_sha256 del release.")
    if expected_sha256 is not None and recalculated != _require_sha256(expected_sha256):
        raise PermissionError("El checksum proporcionado no corresponde al release exacto.")


def _build_release_in_connection(
    connection: Connection[Any],
    plan_id: uuid.UUID,
    expected_fingerprint: str,
    version: str,
    actor: str,
    reason: str,
    *,
    brand_name: str = BRAND,
) -> dict[str, Any]:
    version = _require_version(version)
    actor = _require_text(actor, "actor")
    reason = _require_text(reason, "reason")
    plan = _load_applied_plan(connection, plan_id, expected_fingerprint)
    brand = _resolve_brand(connection, plan["source_system_id"], brand_name)
    records = _load_release_records(connection, brand["brand_id"])
    items = _release_items(records)
    definition = {
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "release_hash_algorithm": RELEASE_HASH_ALGORITHM,
        "source_kind": "applied_catalog",
        "source_plan_id": str(plan_id),
        "source_plan_fingerprint_sha256": plan["approval_fingerprint_sha256"],
        "source_import_batch_id": str(plan["import_batch_id"]),
        "contract_version": plan["contract_version"],
        "rules_version": plan["rules_version"],
        "selection": {
            "brand": brand["normalized_name"],
            "product_catalog_status": "active",
            "variant_catalog_status": "active_when_present",
            "reference_type": "internal",
            "reference_review_status": "approved",
            "primary_reference_required": True,
        },
        "item_count": len(items),
    }
    release_id = uuid.uuid5(
        RELEASE_NAMESPACE, f"{brand['brand_id']}:{version}"
    )
    snapshot_sha256 = release_snapshot_sha256(
        brand["brand_id"], version, definition, items
    )
    existing = connection.execute(
        """
        SELECT catalog_release_id
        FROM perfect_catalog.catalog_release
        WHERE brand_id=%s AND version=%s
        """,
        (brand["brand_id"], version),
    ).fetchone()
    if existing is not None:
        release, persisted_items = _load_release(connection, existing[0], lock=True)
        _verify_release(release, persisted_items)
        if (
            release["catalog_release_id"] != release_id
            or release["definition"] != definition
            or release["snapshot_sha256"] != snapshot_sha256
        ):
            raise RuntimeError("La versión ya existe con contenido diferente.")
        return {
            "release_id": str(release_id),
            "status": "already_built",
            "release_status": release["status"],
            "version": version,
            "item_count": len(items),
            "snapshot_sha256": snapshot_sha256,
        }

    now = datetime.now(UTC)
    connection.execute(
        """
        INSERT INTO perfect_catalog.catalog_release (
            catalog_release_id, brand_id, version, status, definition,
            created_at, created_by, notes, snapshot_sha256
        ) VALUES (%s,%s,%s,'draft',%s,%s,%s,%s,%s)
        """,
        (
            release_id,
            brand["brand_id"],
            version,
            Jsonb(definition),
            now,
            actor,
            reason,
            snapshot_sha256,
        ),
    )
    for item in items:
        target_id = item.get("product_variant_id") or item["product_template_id"]
        item_id = uuid.uuid5(release_id, f"item:{target_id}")
        connection.execute(
            """
            INSERT INTO perfect_catalog.catalog_release_item (
                catalog_release_item_id, catalog_release_id, brand_id,
                product_template_id, product_variant_id, item_order,
                snapshot_schema_version, snapshot_data, snapshot_sha256,
                section_key, grouping_keys, source_import_batch_id
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                item_id,
                release_id,
                brand["brand_id"],
                item["product_template_id"],
                item.get("product_variant_id"),
                item["item_order"],
                item["snapshot_schema_version"],
                Jsonb(item["snapshot_data"]),
                item["snapshot_sha256"],
                item.get("section_key"),
                Jsonb(item["grouping_keys"]),
                item.get("source_import_batch_id"),
            ),
        )
    release = {
        "catalog_release_id": release_id,
        "brand_id": brand["brand_id"],
        "version": version,
        "status": "draft",
        "definition": definition,
        "snapshot_sha256": snapshot_sha256,
    }
    _insert_release_audit(
        connection,
        release=release,
        event_type="catalog_release.built",
        actor=actor,
        reason=reason,
        before_data=None,
        after_data={
            "status": "draft",
            "version": version,
            "item_count": len(items),
            "snapshot_sha256": snapshot_sha256,
        },
        correlation_id=uuid.uuid4(),
    )
    return {
        "release_id": str(release_id),
        "status": "built",
        "release_status": "draft",
        "version": version,
        "item_count": len(items),
        "snapshot_sha256": snapshot_sha256,
    }


def build_release(
    plan_id: uuid.UUID,
    expected_fingerprint: str,
    version: str,
    actor: str,
    reason: str,
    config: DatabaseConfig,
    password: str,
    *,
    brand_name: str = BRAND,
) -> dict[str, Any]:
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        return _build_release_in_connection(
            connection,
            plan_id,
            expected_fingerprint,
            version,
            actor,
            reason,
            brand_name=brand_name,
        )


def inspect_release(
    release_id: uuid.UUID, config: DatabaseConfig, password: str
) -> dict[str, Any]:
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        release, items = _load_release(connection, release_id, lock=False)
        _verify_release(release, items)
        return {
            "release_id": str(release_id),
            "brand_id": str(release["brand_id"]),
            "version": release["version"],
            "release_status": release["status"],
            "item_count": len(items),
            "snapshot_sha256": release["snapshot_sha256"],
            "definition": release["definition"],
            "created_at": release["created_at"].isoformat(),
            "created_by": release["created_by"],
            "published_at": (
                release["published_at"].isoformat()
                if release["published_at"] is not None
                else None
            ),
            "published_by": release["published_by"],
            "archived_at": (
                release["archived_at"].isoformat()
                if release["archived_at"] is not None
                else None
            ),
            "archived_by": release["archived_by"],
        }


def load_published_release(
    release_id: uuid.UUID, config: DatabaseConfig, password: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Carga un release publicado y vuelve a verificar su contenido antes de exportarlo."""
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        release, items = _load_release(connection, release_id, lock=False)
        _verify_release(release, items)
    if release["status"] != "published":
        raise PermissionError("Solo se puede exportar un release publicado.")
    return release, items


def list_catalog_releases(
    config: DatabaseConfig, password: str, *, limit: int = 100
) -> list[dict[str, Any]]:
    if limit < 1 or limit > 500:
        raise ValueError("limit debe estar entre 1 y 500.")
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT r.catalog_release_id, r.brand_id, r.version, r.status,
                       r.snapshot_sha256, r.created_at, r.created_by,
                       r.published_at, r.published_by,
                       count(i.catalog_release_item_id) AS item_count
                FROM perfect_catalog.catalog_release AS r
                LEFT JOIN perfect_catalog.catalog_release_item AS i
                  ON i.catalog_release_id = r.catalog_release_id
                GROUP BY r.catalog_release_id
                ORDER BY r.created_at DESC, r.catalog_release_id DESC
                LIMIT %s
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]


def _verify_source_plan_for_release(
    connection: Connection[Any], release: dict[str, Any]
) -> dict[str, Any]:
    definition = release["definition"]
    try:
        plan_id = uuid.UUID(str(definition["source_plan_id"]))
        fingerprint = str(definition["source_plan_fingerprint_sha256"])
    except (KeyError, ValueError) as exc:
        raise RuntimeError("El release no conserva un plan fuente válido.") from exc
    return _load_applied_plan(connection, plan_id, fingerprint)


def _archive_other_published_releases(
    connection: Connection[Any],
    release: dict[str, Any],
    actor: str,
    reason: str,
    correlation_id: uuid.UUID,
) -> list[str]:
    rows = connection.execute(
        """
        SELECT catalog_release_id
        FROM perfect_catalog.catalog_release
        WHERE brand_id=%s AND status='published' AND catalog_release_id<>%s
        ORDER BY published_at, catalog_release_id
        FOR UPDATE
        """,
        (release["brand_id"], release["catalog_release_id"]),
    ).fetchall()
    archived: list[str] = []
    for (old_id,) in rows:
        old_release, old_items = _load_release(connection, old_id, lock=False)
        _verify_release(old_release, old_items)
        now = datetime.now(UTC)
        connection.execute(
            """
            UPDATE perfect_catalog.catalog_release
            SET status='archived', archived_at=%s, archived_by=%s
            WHERE catalog_release_id=%s AND status='published'
            """,
            (now, actor, old_id),
        )
        _insert_release_audit(
            connection,
            release=old_release,
            event_type="catalog_release.archived",
            actor=actor,
            reason=f"Archivado al publicar {release['catalog_release_id']}: {reason}",
            before_data={"status": "published"},
            after_data={"status": "archived", "superseded_by": release["catalog_release_id"]},
            correlation_id=correlation_id,
        )
        archived.append(str(old_id))
    return archived


def _publish_release_in_connection(
    connection: Connection[Any],
    release_id: uuid.UUID,
    expected_sha256: str,
    actor: str,
    reason: str,
) -> dict[str, Any]:
    actor = _require_text(actor, "actor")
    reason = _require_text(reason, "reason")
    release, items = _load_release(connection, release_id, lock=True)
    _verify_release(release, items, expected_sha256)
    _verify_source_plan_for_release(connection, release)
    if release["status"] == "published":
        return {
            "release_id": str(release_id),
            "status": "already_published",
            "snapshot_sha256": release["snapshot_sha256"],
        }
    if release["status"] != "draft":
        raise PermissionError(
            f"Publicación rechazada: el release está en {release['status']!r}."
        )
    correlation_id = uuid.uuid4()
    archived = _archive_other_published_releases(
        connection, release, actor, reason, correlation_id
    )
    now = datetime.now(UTC)
    changed = connection.execute(
        """
        UPDATE perfect_catalog.catalog_release
        SET status='published', published_at=%s, published_by=%s
        WHERE catalog_release_id=%s AND status='draft'
        """,
        (now, actor, release_id),
    ).rowcount
    if changed != 1:
        raise RuntimeError("El release cambió de estado mientras se publicaba.")
    _insert_release_audit(
        connection,
        release=release,
        event_type="catalog_release.published",
        actor=actor,
        reason=reason,
        before_data={"status": "draft"},
        after_data={
            "status": "published",
            "snapshot_sha256": release["snapshot_sha256"],
            "item_count": len(items),
            "archived_release_ids": archived,
        },
        correlation_id=correlation_id,
    )
    return {
        "release_id": str(release_id),
        "status": "published",
        "snapshot_sha256": release["snapshot_sha256"],
        "archived_release_ids": archived,
    }


def publish_release(
    release_id: uuid.UUID,
    expected_sha256: str,
    actor: str,
    reason: str,
    config: DatabaseConfig,
    password: str,
) -> dict[str, Any]:
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        return _publish_release_in_connection(
            connection, release_id, expected_sha256, actor, reason
        )


def _archive_release_in_connection(
    connection: Connection[Any],
    release_id: uuid.UUID,
    expected_sha256: str,
    actor: str,
    reason: str,
) -> dict[str, Any]:
    actor = _require_text(actor, "actor")
    reason = _require_text(reason, "reason")
    release, items = _load_release(connection, release_id, lock=True)
    _verify_release(release, items, expected_sha256)
    if release["status"] == "archived":
        return {
            "release_id": str(release_id),
            "status": "already_archived",
            "snapshot_sha256": release["snapshot_sha256"],
        }
    if release["status"] != "published":
        raise PermissionError(
            f"Archivo rechazado: el release está en {release['status']!r}."
        )
    now = datetime.now(UTC)
    changed = connection.execute(
        """
        UPDATE perfect_catalog.catalog_release
        SET status='archived', archived_at=%s, archived_by=%s
        WHERE catalog_release_id=%s AND status='published'
        """,
        (now, actor, release_id),
    ).rowcount
    if changed != 1:
        raise RuntimeError("El release cambió de estado mientras se archivaba.")
    _insert_release_audit(
        connection,
        release=release,
        event_type="catalog_release.archived",
        actor=actor,
        reason=reason,
        before_data={"status": "published"},
        after_data={"status": "archived"},
        correlation_id=uuid.uuid4(),
    )
    return {
        "release_id": str(release_id),
        "status": "archived",
        "snapshot_sha256": release["snapshot_sha256"],
    }


def archive_release(
    release_id: uuid.UUID,
    expected_sha256: str,
    actor: str,
    reason: str,
    config: DatabaseConfig,
    password: str,
) -> dict[str, Any]:
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        return _archive_release_in_connection(
            connection, release_id, expected_sha256, actor, reason
        )
