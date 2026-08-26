from __future__ import annotations

import hashlib
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from tools.odoo_profiler import profile_file

from .config import DatabaseConfig
from .importer import DEFAULT_MAX_PILOT_ROWS, run_dry_run
from .tabular_detection import detect_columns


PROMOTION_ALGORITHM = "intake-to-dry-run-v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reason(value: str) -> str:
    value = str(value or "").strip()
    if not 4 <= len(value) <= 500:
        raise ValueError("El motivo de promoción debe tener entre 4 y 500 caracteres.")
    return value


def _actor(value: str) -> str:
    value = str(value or "").strip()
    if not value or len(value) > 120:
        raise ValueError("El actor de promoción no es válido.")
    return value


def _confined(root: Path, relative: str) -> Path:
    parts = PurePosixPath(str(relative)).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("La ruta del objeto en cuarentena no es válida.")
    candidate = root.joinpath(*parts).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("La ruta del objeto sale de la raíz de intake.")
    return candidate


def _profile_suggestions(profile: dict[str, Any]) -> dict[str, Any]:
    sheets = []
    for sheet in profile["workbook"]["sheets"]:
        headers = sheet.get("headers") or []
        sheets.append({"name": sheet["name"], "columns": detect_columns(headers)})
    return {"algorithm": PROMOTION_ALGORITHM, "sheets": sheets}


def promote_intake_to_dry_run(
    submission_id: uuid.UUID,
    intake_root: Path,
    config: DatabaseConfig,
    password: str,
    output_dir: Path,
    *,
    actor: str,
    reason: str,
    max_rows: int = DEFAULT_MAX_PILOT_ROWS,
) -> dict[str, Any]:
    actor, reason = _actor(actor), _reason(reason)
    root = Path(intake_root).resolve()
    promotion_id = uuid.uuid4()
    processing_path: Path | None = None
    dry_run: dict[str, Any] | None = None
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (str(submission_id),))
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT p.intake_promotion_id, p.import_plan_id, p.import_batch_id,
                       p.profile_report, p.column_suggestions, p.processing_relpath,
                       p.promoted_at, p.promoted_by
                FROM perfect_catalog.intake_promotion AS p
                WHERE p.intake_submission_id=%s
                """,
                (submission_id,),
            )
            existing = cursor.fetchone()
            if existing:
                result = dict(existing)
                for key in ("intake_promotion_id", "import_plan_id", "import_batch_id"):
                    result[key] = str(result[key])
                result["promoted_at"] = result["promoted_at"].isoformat()
                return {"status": "already_promoted", **result}
            cursor.execute(
                """
                SELECT s.intake_submission_id, s.intake_asset_id, s.intake_kind,
                       s.original_name, s.extension, s.size_bytes, s.sha256,
                       s.validation_status, a.storage_relpath
                FROM perfect_catalog.intake_submission AS s
                LEFT JOIN perfect_catalog.intake_asset AS a ON a.intake_asset_id=s.intake_asset_id
                WHERE s.intake_submission_id=%s
                """,
                (submission_id,),
            )
            submission = cursor.fetchone()
        if submission is None:
            raise ValueError("No existe el ingreso solicitado.")
        if submission["validation_status"] != "quarantined" or submission["intake_kind"] != "odoo_data":
            raise PermissionError("Sólo se promueven datos Odoo aceptados y en cuarentena.")
        source = _confined(root, submission["storage_relpath"])
        if not source.is_file() or source.stat().st_size != submission["size_bytes"]:
            raise RuntimeError("El objeto en cuarentena falta o no coincide con su tamaño registrado.")
        if _sha256(source) != submission["sha256"]:
            raise RuntimeError("El objeto en cuarentena no coincide con su SHA-256 registrado.")

        relative = PurePosixPath("processing", str(promotion_id), submission["original_name"])
        processing_path = _confined(root, relative.as_posix())
        processing_path.parent.mkdir(parents=True, exist_ok=False)
        shutil.copyfile(source, processing_path)
        if _sha256(processing_path) != submission["sha256"]:
            raise RuntimeError("La copia de procesamiento no coincide con el objeto en cuarentena.")
        try:
            profile = profile_file(processing_path)
            suggestions = _profile_suggestions(profile)
            dry_run = run_dry_run(processing_path, config, password, output_dir, max_rows)
            if dry_run["source_sha256_before"] != submission["sha256"] or not dry_run["source_unchanged"]:
                raise RuntimeError("El dry-run no conserva la identidad del objeto promovido.")
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO perfect_catalog.intake_promotion (
                        intake_promotion_id, intake_submission_id, intake_asset_id,
                        import_batch_id, import_plan_id, source_sha256, processing_relpath,
                        profile_report, column_suggestions, promoted_by, reason, promoted_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        promotion_id, submission_id, submission["intake_asset_id"],
                        uuid.UUID(dry_run["batch_id"]), uuid.UUID(dry_run["plan_id"]),
                        submission["sha256"], relative.as_posix(), Jsonb(profile),
                        Jsonb(suggestions), actor, reason, datetime.now(UTC),
                    ),
                )
            connection.commit()
            return {
                "status": "promoted",
                "intake_promotion_id": str(promotion_id),
                "intake_submission_id": str(submission_id),
                "processing_relpath": relative.as_posix(),
                "column_suggestions": suggestions,
                "profile": profile,
                "dry_run": dry_run,
            }
        except Exception:
            # Si el dry-run ya fue persistido, import_file conserva esta ruta como evidencia.
            # Un fallo posterior no debe convertir ese registro en una referencia rota.
            if dry_run is None and processing_path.exists():
                processing_path.unlink()
            if dry_run is None and processing_path.parent.exists():
                processing_path.parent.rmdir()
            raise
