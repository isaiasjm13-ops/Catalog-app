from __future__ import annotations

import json
import re
import unicodedata
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import psycopg
from psycopg import Connection
from psycopg.types.json import Jsonb

from tools.odoo_profiler import read_tabular_source, sha256_file

from .canonical import canonical_sha256, normalize_name, normalize_reference
from .config import DatabaseConfig
from .name_parser import parse_product_name


CONTRACT_VERSION = "natsuki-empaques-v0.2"
RULES_VERSION = "normalization-v0.4"
SUPPORTED_RULES_VERSIONS = frozenset({"normalization-v0.3", RULES_VERSION})
PROFILER_VERSION = "0.1"
SOURCE_CODE = "odoo"
SOURCE_MODEL = "product.template"
BRAND = "NATSUKI"
FAMILY = "empaques"
NAMESPACE = uuid.UUID("f4d6e64a-51b1-4f1c-8d2f-f87337ab05f9")

EXPECTED_HEADERS = (
    "Moneda",
    "Estado de la actividad",
    "Categoría de producto",
    "Favorito",
    "Nombre",
    "Referencia interna",
    "# Variantes de producto",
    "Cantidad real",
    "Unidad de medida",
    "Cantidad disponible",
    "Imagen 128",
    "Última actualización el",
    "Mostrar botón de estado de cantidad real",
)

REQUIRED_HEADERS = (
    "Nombre",
    "Referencia interna",
)

DEFAULT_MAX_PILOT_ROWS = 5_000

BUSINESS_TABLES = (
    "product_template",
    "product_variant",
    "product_reference",
    "inventory_snapshot",
    "media_asset",
    "product_media",
    "catalog_release",
    "catalog_release_item",
)


@dataclass(frozen=True)
class PreparedRow:
    source_row_number: int
    raw_values: dict[str, Any]
    raw_excel_serials: dict[str, Any]
    structural_metadata: dict[str, Any]
    row_sha256: str
    normalized: dict[str, Any]
    issue_specs: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class HeaderContract:
    headers: tuple[str, ...]
    missing_optional: tuple[str, ...]
    unknown: tuple[str, ...]
    reordered: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "headers": list(self.headers),
            "missing_optional": list(self.missing_optional),
            "unknown": list(self.unknown),
            "reordered": self.reordered,
        }


def _header_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _json_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    key = _header_key(value)
    if key in {"true", "verdadero", "si", "1"}:
        return True
    if key in {"false", "falso", "no", "0"}:
        return False
    return None


def reference_candidates(enrichment: dict[str, Any]) -> list[dict[str, Any]]:
    """Convierte inferencias del parser en candidatos tipados; nunca los aprueba."""
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(value: Any, kind: str, confidence: Any, source: str) -> None:
        original = str(value or "").strip()
        normalized = normalize_reference(original)
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        candidates.append({
            "reference_type": kind,
            "value_original": original,
            "value_normalized": normalized,
            "confidence": float(confidence),
            "source": source,
            "review_status": "pending",
        })

    for value in enrichment.get("oem_references") or []:
        add(value, "oem", 0.82, "product_name")
    for value in enrichment.get("fmsi_references") or []:
        add(value, "fmsi", 0.82, "product_name")
    for item in enrichment.get("reference_suggestions") or []:
        kind = str(item.get("kind") or "alternate")
        add(
            item.get("value"),
            "additional" if kind == "additional" else "fmsi" if kind == "fmsi" else "alternate",
            item.get("confidence", 0.5),
            str(item.get("source") or "product_name"),
        )
    return candidates


def _as_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or _is_empty(value):
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        number = float(str(value).strip().replace(",", "."))
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def analyze_headers(headers: Iterable[Any]) -> HeaderContract:
    actual = tuple(str(value or "").strip() for value in headers)
    if not actual:
        raise ValueError("El archivo no contiene encabezados.")
    empty_positions = [index for index, value in enumerate(actual, start=1) if not value]
    if empty_positions:
        raise ValueError(f"Hay encabezados vacíos en las columnas {empty_positions}.")

    actual_keys = tuple(map(_header_key, actual))
    duplicate_keys = sorted(key for key, count in Counter(actual_keys).items() if count > 1)
    if duplicate_keys:
        raise ValueError(f"Hay encabezados duplicados después de normalizar: {duplicate_keys!r}.")

    expected_by_key = {_header_key(header): header for header in EXPECTED_HEADERS}
    required_keys = {_header_key(header) for header in REQUIRED_HEADERS}
    missing_required = [
        expected_by_key[key]
        for key in required_keys
        if key not in actual_keys
    ]
    if missing_required:
        raise ValueError(
            "Faltan columnas críticas para identidad y conciliación: "
            f"{sorted(missing_required)!r}."
        )

    missing_optional = tuple(
        header
        for header in EXPECTED_HEADERS
        if _header_key(header) not in actual_keys and _header_key(header) not in required_keys
    )
    unknown = tuple(header for header, key in zip(actual, actual_keys, strict=True) if key not in expected_by_key)
    present_expected_order = tuple(
        _header_key(header)
        for header in EXPECTED_HEADERS
        if _header_key(header) in actual_keys
    )
    observed_expected_order = tuple(key for key in actual_keys if key in expected_by_key)
    return HeaderContract(
        headers=actual,
        missing_optional=missing_optional,
        unknown=unknown,
        reordered=observed_expected_order != present_expected_order,
    )


def validate_headers(headers: Iterable[Any]) -> tuple[str, ...]:
    return analyze_headers(headers).headers


def validate_pilot_row_count(row_count: int, max_rows: int = DEFAULT_MAX_PILOT_ROWS) -> None:
    if max_rows < 1:
        raise ValueError("El límite del piloto debe ser al menos 1.")
    if row_count < 1:
        raise ValueError("El archivo no contiene filas de datos.")
    if row_count > max_rows:
        raise ValueError(
            f"El archivo contiene {row_count} filas y supera el límite de piloto de {max_rows}. "
            "Revise una muestra antes de ampliar explícitamente el límite."
        )


def prepare_rows(sheet_name: str, headers: tuple[str, ...], rows: list[list[Any]], row_numbers: list[int]) -> list[PreparedRow]:
    prepared: list[PreparedRow] = []
    for row, source_row_number in zip(rows, row_numbers, strict=True):
        padded = list(row[: len(headers)]) + [None] * max(0, len(headers) - len(row))
        raw_values = {header: _json_value(value) for header, value in zip(headers, padded, strict=True)}
        values_by_key = {_header_key(header): value for header, value in raw_values.items()}

        def field(header: str) -> Any:
            return values_by_key.get(_header_key(header))

        reference_original = str(field("Referencia interna") or "")
        name_original = str(field("Nombre") or "")
        # El catálogo es de identidad y compatibilidad. Inventario, precio, moneda,
        # responsable, UoM, miniaturas Odoo y metadatos operativos sólo permanecen
        # en el XLSX original/hash; no se normalizan ni generan operaciones.
        image_status = "not_exported"
        raw_excel_serials: dict[str, Any] = {}
        structural_metadata = {
            "column_count": len(headers),
            "sheet_name": sheet_name,
            "image": {
                "status": image_status,
                "payload_character_count": 0,
                "decoded": False,
            },
        }
        issues: list[dict[str, Any]] = []
        if not reference_original.strip():
            issues.append({
                "severity": "error",
                "code": "internal_reference_missing",
                "message": "La referencia interna es obligatoria para la conciliación provisional.",
                "column_name": "Referencia interna",
            })
        if not name_original.strip():
            issues.append({
                "severity": "error",
                "code": "product_name_missing",
                "message": "El nombre del producto está vacío.",
                "column_name": "Nombre",
            })
        enrichment = parse_product_name(
            name_original,
            source_profile="perfect",
            additional_references=field("Referencias Adicionales") or "",
        )
        normalized_internal = normalize_reference(reference_original)
        candidates = [
            candidate for candidate in reference_candidates(enrichment)
            if candidate["value_normalized"] != normalized_internal
        ]
        normalized = {
            "source_model": SOURCE_MODEL,
            "brand": BRAND,
            "family": FAMILY,
            "currency": None,
            "activity_state": None,
            "category_path": field("Categoría de producto"),
            "is_favorite": None,
            "name_original": name_original,
            "name_normalized": normalize_name(name_original),
            "internal_reference_original": reference_original,
            "internal_reference_normalized": normalized_internal,
            "variant_count_observed": _as_number(field("# Variantes de producto")),
            "quantity_on_hand": None,
            "uom_original": None,
            "quantity_available": None,
            "image_status": image_status,
            "source_date_serial": None,
            "source_updated_at": None,
            "show_quantity_status": None,
            "source_active": None,
            "catalog_status": "pending_review",
            "name_enrichment": enrichment,
            "reference_candidates": candidates,
        }
        row_evidence = {
            "headers": list(headers),
            "values": raw_values,
            "source_row_number": source_row_number,
            "sheet_name": sheet_name,
        }
        prepared.append(
            PreparedRow(
                source_row_number=source_row_number,
                raw_values=raw_values,
                raw_excel_serials=raw_excel_serials,
                structural_metadata=structural_metadata,
                row_sha256=canonical_sha256(row_evidence),
                normalized=normalized,
                issue_specs=tuple(issues),
            )
        )
    return prepared


def future_product_id(plan_id: uuid.UUID, normalized_reference: str) -> uuid.UUID:
    return uuid.uuid5(plan_id, f"product-template:{normalized_reference}")


def plan_item_hash(item: dict[str, Any]) -> str:
    evidence = {
        key: value
        for key, value in item.items()
        if key not in {"import_plan_item_id", "created_at", "item_sha256"}
    }
    return canonical_sha256(evidence)


def plan_hash(
    file_sha256: str,
    items: list[dict[str, Any]],
    contract_version: str = CONTRACT_VERSION,
    rules_version: str = RULES_VERSION,
) -> str:
    return canonical_sha256({
        "contract_version": contract_version,
        "rules_version": rules_version,
        "file_sha256": file_sha256,
        "items": [item["item_sha256"] for item in items],
    })


def approval_fingerprint(
    file_sha256: str,
    plan_sha256: str,
    contract_version: str = CONTRACT_VERSION,
    rules_version: str = RULES_VERSION,
) -> str:
    return canonical_sha256({
        "contract_version": contract_version,
        "rules_version": rules_version,
        "file_sha256": file_sha256,
        "plan_sha256": plan_sha256,
    })


def _business_counts(connection: Connection[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    with connection.cursor() as cursor:
        for table in BUSINESS_TABLES:
            cursor.execute(f"SELECT count(*) FROM perfect_catalog.{table}")
            counts[table] = int(cursor.fetchone()[0])
    return counts


def _existing_products(
    connection: Connection[Any], source_system_id: uuid.UUID,
    references: list[str], company_id: uuid.UUID | None = None,
) -> dict[str, list[uuid.UUID]]:
    matches: dict[str, list[uuid.UUID]] = defaultdict(list)
    if not references:
        return matches
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT pr.value_normalized, pr.product_template_id
            FROM perfect_catalog.product_reference AS pr
            JOIN perfect_catalog.brand AS b ON b.brand_id = pr.brand_id
            WHERE pr.source_system_id = %s
              AND b.normalized_name = %s
              AND (%s::uuid IS NULL OR b.company_id = %s)
              AND pr.reference_type = 'internal'
              AND pr.value_normalized = ANY(%s)
            ORDER BY pr.value_normalized, pr.product_template_id
            """,
            (source_system_id, BRAND, company_id, company_id, references),
        )
        for reference, product_id in cursor.fetchall():
            matches[str(reference)].append(product_id)
    return matches


def _existing_reference_owners(
    connection: Connection[Any], company_id: uuid.UUID,
    references: list[str],
) -> dict[str, set[uuid.UUID]]:
    owners: dict[str, set[uuid.UUID]] = defaultdict(set)
    if not references:
        return owners
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT pr.value_normalized, pr.product_template_id
            FROM perfect_catalog.product_reference AS pr
            JOIN perfect_catalog.brand AS b ON b.brand_id=pr.brand_id
            WHERE b.company_id=%s
              AND COALESCE(pr.review_status, 'pending') <> 'rejected'
              AND pr.value_normalized = ANY(%s)
            ORDER BY pr.value_normalized, pr.product_template_id
            """,
            (company_id, references),
        )
        for reference, product_id in cursor.fetchall():
            owners[str(reference)].add(product_id)
    return owners


def _make_item(
    plan_id: uuid.UUID,
    file_id: uuid.UUID,
    staging_row_id: uuid.UUID,
    order: int,
    operation: str,
    planned_product_id: uuid.UUID,
    resolved_product_id: uuid.UUID | None,
    proposed: dict[str, Any],
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    item = {
        "import_plan_item_id": uuid.uuid5(plan_id, f"item:{order}:{operation}:{staging_row_id}"),
        "import_plan_id": plan_id,
        "import_file_id": file_id,
        "item_order": order,
        "staging_row_id": staging_row_id,
        "resolved_product_template_id": resolved_product_id,
        "resolved_product_variant_id": None,
        "planned_product_template_id": planned_product_id,
        "planned_product_variant_id": None,
        "operation_type": operation,
        "before_values": {},
        "proposed_values": proposed,
        "issues": issues,
        "requires_review": True,
    }
    item["item_sha256"] = plan_item_hash(item)
    return item


def _write_reports(summary: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"odoo_import_plan_{summary['plan_id']}"
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Odoo import dry-run",
        "",
        f"- Plan ID: `{summary['plan_id']}`",
        f"- Estado: `{summary['plan_status']}`",
        f"- Plan SHA-256: `{summary['plan_sha256']}`",
        f"- Fingerprint: `{summary['approval_fingerprint_sha256']}`",
        f"- Archivo SHA-256 antes: `{summary['source_sha256_before']}`",
        f"- Archivo SHA-256 después: `{summary['source_sha256_after']}`",
        f"- Columnas opcionales ausentes: {', '.join(summary['header_contract']['missing_optional']) or 'ninguna'}",
        f"- Columnas nuevas conservadas: {', '.join(summary['header_contract']['unknown']) or 'ninguna'}",
        f"- Columnas conocidas reordenadas: {'sí' if summary['header_contract']['reordered'] else 'no'}",
        f"- Filas leídas / staging / clasificadas: {summary['rows_read']} / {summary['staging_rows']} / {summary['classified_rows']}",
        f"- Altas propuestas: {summary['plan_counts']['create']}",
        f"- Snapshots propuestos: {summary['plan_counts']['inventory_snapshot']}",
        f"- Medios pendientes: {summary['plan_counts']['media_pending']}",
        f"- Medios ausentes: {summary['media_absent']}",
        f"- Columna de medios no exportada: {summary['media_not_exported']}",
        f"- Warnings / errores / bloqueos / conflictos: {summary['issues']['warning']} / {summary['issues']['error']} / {summary['plan_counts']['blocked']} / {summary['plan_counts']['conflict']}",
        f"- Grupos de nombres duplicados: {summary['duplicate_name_groups']}",
        f"- Referencias únicas: {summary['unique_references']}",
        f"- Parser vehicular: `{summary['name_enrichment']['parser_version']}` (`pending_review`)",
        f"- Aplicaciones sugeridas / confianza alta: {summary['name_enrichment']['application_suggestions']} / {summary['name_enrichment']['high_confidence_applications']}",
        f"- Motores sugeridos / filas con años / filas con posición: {summary['name_enrichment']['engine_suggestions']} / {summary['name_enrichment']['with_year_range']} / {summary['name_enrichment']['with_position']}",
        f"- OEM / FMSI / referencias adicionales sugeridas: {summary['name_enrichment']['oem_reference_suggestions']} / {summary['name_enrichment']['fmsi_reference_suggestions']} / {summary['name_enrichment']['dedicated_additional_references']}",
        f"- Candidatos A1 tipados pendientes: {summary['name_enrichment'].get('reference_candidates', 0)}",
        f"- Escrituras empresariales: {summary['business_writes']}",
        "",
        "El contenido Base64 no se incluye en este reporte y ninguna imagen fue decodificada.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def run_dry_run(
    source_path: Path,
    config: DatabaseConfig,
    password: str,
    output_dir: Path,
    max_rows: int = DEFAULT_MAX_PILOT_ROWS,
    *,
    company_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    if company_id is None:
        raise ValueError("company_id es obligatorio para generar un dry-run nuevo.")
    source_path = source_path.resolve(strict=True)
    source_sha_before = sha256_file(source_path)
    sheets = read_tabular_source(source_path)
    source_sha_after_read = sha256_file(source_path)
    if source_sha_before != source_sha_after_read:
        raise RuntimeError("El hash del archivo cambió durante la lectura; el dry-run fue cancelado.")
    if len(sheets) != 1 or not sheets[0].rows:
        raise ValueError("El contrato requiere exactamente una hoja no vacía.")
    sheet = sheets[0]
    header_contract = analyze_headers(sheet.rows[0])
    headers = header_contract.headers
    prepared = prepare_rows(sheet.name, headers, sheet.rows[1:], sheet.row_numbers[1:])
    validate_pilot_row_count(len(prepared), max_rows)

    batch_id = uuid.uuid4()
    file_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    now = datetime.now(UTC)
    source_id_default = uuid.uuid5(NAMESPACE, "source-system:odoo")
    storage_uri = (
        source_path.relative_to(Path.cwd()).as_posix()
        if source_path.is_relative_to(Path.cwd())
        else str(source_path)
    )

    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        business_before = _business_counts(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO perfect_catalog.source_system (
                    source_system_id, code, name, system_type, timezone_name, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (code) DO UPDATE SET
                    name = EXCLUDED.name,
                    system_type = EXCLUDED.system_type,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING source_system_id
                """,
                (source_id_default, SOURCE_CODE, "Odoo", "erp", "America/Panama", Jsonb({"source_model": SOURCE_MODEL})),
            )
            source_system_id = cursor.fetchone()[0]
            cursor.execute(
                "SELECT import_file_id FROM perfect_catalog.import_file WHERE sha256 = %s ORDER BY received_at, import_file_id LIMIT 1",
                (source_sha_before,),
            )
            duplicate_row = cursor.fetchone()
            duplicate_of = duplicate_row[0] if duplicate_row else None
            scope = {
                "brand": BRAND,
                "family": FAMILY,
                "source_model": SOURCE_MODEL,
                "filters": {
                    "brand_equals": BRAND,
                    "product_category_contains": "empaque",
                    "quantity_filter": None,
                    "exclude_missing_barcode": False,
                    "exclude_missing_image": False,
                },
            }
            cursor.execute(
                """
                INSERT INTO perfect_catalog.import_batch (
                    import_batch_id, source_system_id, mode, status, scope,
                    started_at, requested_by, profiler_version, rules_version
                ) VALUES (%s, %s, 'dry_run', 'staging', %s, %s, %s, %s, %s)
                """,
                (batch_id, source_system_id, Jsonb(scope), now, "interactive-user", PROFILER_VERSION, RULES_VERSION),
            )
            cursor.execute(
                """
                INSERT INTO perfect_catalog.import_file (
                    import_file_id, import_batch_id, original_name, storage_uri,
                    size_bytes, sha256, media_type, received_at, sheet_count,
                    workbook_metadata, duplicate_of_file_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    file_id,
                    batch_id,
                    source_path.name,
                    storage_uri,
                    source_path.stat().st_size,
                    source_sha_before,
                    {
                        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        ".csv": "text/csv",
                        ".tsv": "text/tab-separated-values",
                    }.get(source_path.suffix.lower(), "application/octet-stream"),
                    now,
                    len(sheets),
                    Jsonb({"sheet_names": [sheet.name], "formula_count": sheet.formula_count}),
                    duplicate_of,
                ),
            )

            staging_ids: list[uuid.UUID] = []
            result_ids: list[uuid.UUID] = []
            for row in prepared:
                staging_id = uuid.uuid4()
                result_id = uuid.uuid4()
                staging_ids.append(staging_id)
                result_ids.append(result_id)
                cursor.execute(
                    """
                    INSERT INTO perfect_catalog.staging_row (
                        staging_row_id, import_file_id, sheet_name, source_row_number,
                        raw_headers, raw_values, raw_excel_serials, structural_metadata, row_sha256
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        staging_id,
                        file_id,
                        sheet.name,
                        row.source_row_number,
                        Jsonb(list(headers)),
                        Jsonb(row.raw_values),
                        Jsonb(row.raw_excel_serials),
                        Jsonb(row.structural_metadata),
                        row.row_sha256,
                    ),
                )
                result_status = "valid" if not row.issue_specs else "valid_with_warnings"
                if any(issue["severity"] in {"error", "fatal"} for issue in row.issue_specs):
                    result_status = "invalid"
                result_evidence = {
                    "normalized_data": row.normalized,
                    "status": result_status,
                    "contract_version": CONTRACT_VERSION,
                    "rules_version": RULES_VERSION,
                }
                cursor.execute(
                    """
                    INSERT INTO perfect_catalog.staging_row_result (
                        staging_row_result_id, staging_row_id, import_batch_id, import_file_id,
                        contract_version, rules_version, processing_stage, attempt_number,
                        status, normalized_data, result_sha256, processor_version, metadata, completed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, 'reconciled', 1, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        result_id,
                        staging_id,
                        batch_id,
                        file_id,
                        CONTRACT_VERSION,
                        RULES_VERSION,
                        result_status,
                        Jsonb(row.normalized),
                        canonical_sha256(result_evidence),
                        "perfect-catalog-importer/0.1.0",
                        Jsonb({"image_decoded": False}),
                        datetime.now(UTC),
                    ),
                )
                for issue in row.issue_specs:
                    cursor.execute(
                        """
                        INSERT INTO perfect_catalog.import_issue (
                            import_issue_id, import_batch_id, import_file_id, staging_row_id,
                            staging_row_result_id, severity, code, message, status, column_name, details
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'open', %s, %s)
                        """,
                        (
                            uuid.uuid4(),
                            batch_id,
                            file_id,
                            staging_id,
                            result_id,
                            issue["severity"],
                            issue["code"],
                            issue["message"],
                            issue.get("column_name"),
                            Jsonb({"source_row_number": row.source_row_number}),
                        ),
                    )

            references = [row.normalized["internal_reference_normalized"] for row in prepared]
            existing = _existing_products(
                connection, source_system_id, references, company_id=company_id,
            )
            candidate_products: dict[str, set[str]] = defaultdict(set)
            candidate_values: list[str] = []
            for row in prepared:
                internal = row.normalized["internal_reference_normalized"]
                for candidate in row.normalized["reference_candidates"]:
                    value = candidate["value_normalized"]
                    candidate_products[value].add(internal)
                    candidate_values.append(value)
            existing_candidate_owners = _existing_reference_owners(
                connection, company_id, sorted(set(candidate_values)),
            )
            items: list[dict[str, Any]] = []
            order = 0
            for row, staging_id in zip(prepared, staging_ids, strict=True):
                reference = row.normalized["internal_reference_normalized"]
                matches = existing.get(reference, [])
                if len(matches) > 1:
                    order += 1
                    planned_id = uuid.uuid5(plan_id, f"conflict:{reference}")
                    items.append(_make_item(
                        plan_id, file_id, staging_id, order, "conflict", planned_id, None,
                        {"internal_reference_normalized": reference},
                        [{"code": "ambiguous_reference", "severity": "error"}],
                    ))
                    continue
                resolved_id = matches[0] if matches else None
                planned_id = resolved_id or future_product_id(plan_id, reference)
                row_issue_codes = [
                    {"code": issue["code"], "severity": issue["severity"]}
                    for issue in row.issue_specs
                ]
                candidate_conflicts = sorted({
                    candidate["value_normalized"]
                    for candidate in row.normalized["reference_candidates"]
                    if len(candidate_products[candidate["value_normalized"]]) > 1
                    or any(owner != planned_id for owner in existing_candidate_owners.get(
                        candidate["value_normalized"], set()
                    ))
                })
                if candidate_conflicts:
                    row_issue_codes.append({
                        "code": "cross_reference_conflict",
                        "severity": "error",
                        "references": candidate_conflicts,
                    })
                inventory_complete = False
                if not inventory_complete:
                    row_issue_codes.append({
                        "code": "inventory_snapshot_not_planned",
                        "severity": "warning",
                    })
                if any(issue["severity"] in {"error", "fatal"} for issue in row_issue_codes):
                    order += 1
                    items.append(_make_item(
                        plan_id, file_id, staging_id, order, "blocked", planned_id, resolved_id,
                        {"internal_reference_normalized": reference}, row_issue_codes,
                    ))
                    continue
                operation = "update" if resolved_id else "create"
                order += 1
                items.append(_make_item(
                    plan_id, file_id, staging_id, order, operation, planned_id, resolved_id,
                    {
                        "brand": BRAND,
                        "family": FAMILY,
                        "source_model": SOURCE_MODEL,
                        "name_original": row.normalized["name_original"],
                        "internal_reference_original": row.normalized["internal_reference_original"],
                        "internal_reference_normalized": reference,
                        "category_path": row.normalized["category_path"],
                        "currency": row.normalized["currency"],
                        "activity_state": row.normalized["activity_state"],
                        "is_favorite": row.normalized["is_favorite"],
                        "variant_count_observed": row.normalized["variant_count_observed"],
                        "uom_original": row.normalized["uom_original"],
                        "show_quantity_status": row.normalized["show_quantity_status"],
                        "source_updated_at": row.normalized["source_updated_at"],
                        "catalog_status": "pending_review",
                        "source_active": None,
                        "name_enrichment": row.normalized["name_enrichment"],
                        "reference_candidates": row.normalized["reference_candidates"],
                    },
                    row_issue_codes,
                ))
                if inventory_complete:
                    order += 1
                    items.append(_make_item(
                        plan_id, file_id, staging_id, order, "inventory_snapshot", planned_id, resolved_id,
                        {
                            "quantity_on_hand": row.normalized["quantity_on_hand"],
                            "quantity_available": row.normalized["quantity_available"],
                            "uom_original": row.normalized["uom_original"],
                            "source_date_serial": row.normalized["source_date_serial"],
                            "source_updated_at": None,
                        },
                        [issue for issue in row_issue_codes if issue["code"] == "excel_date_unconverted"],
                    ))
                if row.normalized["image_status"] == "present":
                    order += 1
                    items.append(_make_item(
                        plan_id, file_id, staging_id, order, "media_pending", planned_id, resolved_id,
                        {"status": "presente", "decoded": False}, [],
                    ))

            computed_plan_hash = plan_hash(source_sha_before, items)
            fingerprint = approval_fingerprint(source_sha_before, computed_plan_hash)
            cursor.execute(
                """
                INSERT INTO perfect_catalog.import_plan (
                    import_plan_id, company_id, import_batch_id, import_file_id, file_sha256,
                    contract_version, rules_version, plan_status, plan_sha256,
                    approval_fingerprint_sha256, generated_at, generated_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'awaiting_review', %s, %s, %s, %s)
                """,
                (
                    plan_id, company_id, batch_id, file_id, source_sha_before, CONTRACT_VERSION,
                    RULES_VERSION, computed_plan_hash, fingerprint, datetime.now(UTC),
                    "perfect-catalog-importer/0.1.0",
                ),
            )
            for item in items:
                cursor.execute(
                    """
                    INSERT INTO perfect_catalog.import_plan_item (
                        import_plan_item_id, import_plan_id, import_file_id, item_order,
                        staging_row_id, resolved_product_template_id, resolved_product_variant_id,
                        planned_product_template_id, planned_product_variant_id, operation_type,
                        before_values, proposed_values, issues, requires_review, item_sha256
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        item["import_plan_item_id"], item["import_plan_id"], item["import_file_id"],
                        item["item_order"], item["staging_row_id"], item["resolved_product_template_id"],
                        item["resolved_product_variant_id"], item["planned_product_template_id"],
                        item["planned_product_variant_id"], item["operation_type"],
                        Jsonb(item["before_values"]), Jsonb(item["proposed_values"]),
                        Jsonb(item["issues"]), item["requires_review"], item["item_sha256"],
                    ),
                )

            issue_counts = Counter(
                issue["severity"] for row in prepared for issue in row.issue_specs
            )
            operation_counts = Counter(item["operation_type"] for item in items)
            statistics = {
                "rows_read": len(prepared),
                "staging_rows": len(staging_ids),
                "classified_rows": len(result_ids),
                "issues": dict(issue_counts),
                "plan_items": dict(operation_counts),
            }
            cursor.execute(
                """
                UPDATE perfect_catalog.import_batch
                SET status = 'awaiting_review', finished_at = %s, statistics = %s
                WHERE import_batch_id = %s
                """,
                (datetime.now(UTC), Jsonb(statistics), batch_id),
            )

        business_after = _business_counts(connection)
        if business_before != business_after:
            raise RuntimeError("El dry-run alteró tablas empresariales; transacción cancelada.")
        connection.commit()

    source_sha_final = sha256_file(source_path)
    if source_sha_before != source_sha_final:
        raise RuntimeError("El hash del archivo cambió después del dry-run.")
    names = Counter(row.normalized["name_normalized"] for row in prepared)
    references = [row.normalized["internal_reference_normalized"] for row in prepared]
    enrichments = [row.normalized["name_enrichment"] for row in prepared]
    application_suggestions = [
        application
        for enrichment in enrichments
        for application in enrichment["applications"]
    ]
    summary = {
        "batch_id": str(batch_id),
        "file_id": str(file_id),
        "plan_id": str(plan_id),
        "plan_status": "awaiting_review",
        "contract_version": CONTRACT_VERSION,
        "rules_version": RULES_VERSION,
        "header_contract": header_contract.as_dict(),
        "source_sha256_before": source_sha_before,
        "source_sha256_after": source_sha_final,
        "source_unchanged": source_sha_before == source_sha_final,
        "rows_read": len(prepared),
        "staging_rows": len(prepared),
        "classified_rows": len(prepared),
        "unique_references": len(set(references)),
        "duplicate_name_groups": sum(count > 1 for count in names.values()),
        "name_enrichment": {
            "parser_version": enrichments[0]["parser_version"] if enrichments else None,
            "review_status": "pending_review",
            "application_suggestions": len(application_suggestions),
            "high_confidence_applications": sum(
                application["confidence"] >= 0.8 for application in application_suggestions
            ),
            "engine_suggestions": sum(len(item["engine_suggestions"]) for item in enrichments),
            "with_year_range": sum(
                any(application["years"] is not None for application in item["applications"])
                for item in enrichments
            ),
            "with_position": sum(bool(item["positions"]) for item in enrichments),
            "oem_reference_suggestions": sum(len(item["oem_references"]) for item in enrichments),
            "fmsi_reference_suggestions": sum(len(item["fmsi_references"]) for item in enrichments),
            "dedicated_additional_references": sum(len(item["additional_references"]) for item in enrichments),
            "reference_candidates": sum(len(row.normalized["reference_candidates"]) for row in prepared),
        },
        "media_present": sum(row.normalized["image_status"] == "present" for row in prepared),
        "media_absent": sum(row.normalized["image_status"] == "absent" for row in prepared),
        "media_not_exported": sum(row.normalized["image_status"] == "not_exported" for row in prepared),
        "issues": {severity: int(issue_counts.get(severity, 0)) for severity in ("info", "warning", "error", "fatal")},
        "plan_counts": {operation: int(operation_counts.get(operation, 0)) for operation in (
            "create", "update", "no_change", "inventory_snapshot", "media_pending", "blocked", "conflict"
        )},
        "plan_items_total": len(items),
        "plan_sha256": computed_plan_hash,
        "approval_fingerprint_sha256": fingerprint,
        "business_table_counts_before": business_before,
        "business_table_counts_after": business_after,
        "business_writes": 0,
        "images_decoded": 0,
        "base64_in_report": False,
        "duplicate_of_file_id": str(duplicate_of) if duplicate_of else None,
    }
    report_paths = _write_reports(summary, output_dir)
    summary["reports"] = [str(path) for path in report_paths]
    return summary


def inspect_plan(plan_id: uuid.UUID, config: DatabaseConfig, password: str) -> dict[str, Any]:
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.import_plan_id, p.plan_status, p.plan_sha256,
                       p.approval_fingerprint_sha256, p.file_sha256,
                       p.contract_version, p.rules_version,
                       count(i.import_plan_item_id), bp.code, bp.display_name
                FROM perfect_catalog.import_plan AS p
                LEFT JOIN perfect_catalog.import_plan_item AS i USING (import_plan_id)
                LEFT JOIN perfect_catalog.brand_profile AS bp
                  ON bp.brand_profile_id=p.brand_profile_id
                WHERE p.import_plan_id = %s
                GROUP BY p.import_plan_id, bp.brand_profile_id
                """,
                (plan_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError(f"No existe el plan {plan_id}.")
            return {
                "plan_id": str(row[0]),
                "plan_status": row[1],
                "plan_sha256": row[2],
                "approval_fingerprint_sha256": row[3],
                "file_sha256": row[4],
                "contract_version": row[5],
                "rules_version": row[6],
                "item_count": row[7],
                "brand_profile_code": row[8],
                "brand_profile_name": row[9],
            }


def assert_apply_allowed(plan_id: uuid.UUID, config: DatabaseConfig, password: str) -> None:
    plan = inspect_plan(plan_id, config, password)
    if plan["plan_status"] != "approved":
        raise PermissionError(
            f"Apply rechazado: el plan está en {plan['plan_status']!r}, no en 'approved'."
        )
    raise NotImplementedError("Apply no está implementado ni autorizado en este bloque.")
