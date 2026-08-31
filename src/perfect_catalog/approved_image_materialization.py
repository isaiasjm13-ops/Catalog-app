from __future__ import annotations

import hashlib
import os
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .config import DatabaseConfig
from .intake_promotion import _actor, _confined, _reason, _sha256


def _copy_verified_member(
    archive_path: Path, member_path: str, expected_sha256: str,
    expected_size: int, expected_crc32: str, destination: Path,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        if destination.stat().st_size != expected_size or _sha256(destination) != expected_sha256:
            raise RuntimeError("El objeto content-addressed existente no coincide con su identidad.")
        return
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    digest = hashlib.sha256()
    copied = 0
    try:
        with zipfile.ZipFile(archive_path) as archive:
            try:
                info = archive.getinfo(member_path)
            except KeyError as exc:
                raise RuntimeError("La entrada aprobada ya no existe dentro del ZIP.") from exc
            if info.file_size != expected_size or f"{info.CRC:08x}" != expected_crc32:
                raise RuntimeError("Tamaño o CRC de la entrada no coincide con el índice aprobado.")
            with archive.open(info, "r") as source, temporary.open("xb") as target:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
                    copied += len(chunk)
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
        if copied != expected_size or digest.hexdigest() != expected_sha256:
            raise RuntimeError("Los bytes extraídos no coinciden con el SHA-256 aprobado.")
        if destination.exists():
            if destination.stat().st_size != expected_size or _sha256(destination) != expected_sha256:
                raise RuntimeError("Conflicto al publicar el objeto content-addressed.")
        else:
            temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def materialize_approved_image(
    candidate_id: uuid.UUID, evidence_sha256: str,
    intake_root: Path, image_root: Path,
    config: DatabaseConfig, password: str,
    *, actor: str, reason: str, company_id: uuid.UUID,
) -> dict[str, Any]:
    actor, reason = _actor(actor), _reason(reason)
    if len(evidence_sha256) != 64:
        raise ValueError("evidence_sha256 inválido.")
    intake_root = Path(intake_root).resolve()
    image_root = Path(image_root).resolve()
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 5))",
            (str(candidate_id),),
        )
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT d.image_product_decision_id, d.decision, d.candidate_evidence_sha256,
                       c.image_product_candidate_id, c.evidence_sha256,
                       c.product_template_id, c.product_variant_id,
                       e.image_archive_entry_id, e.member_path, e.original_filename,
                       e.extension, e.media_type, e.uncompressed_size, e.crc32, e.content_sha256,
                       a.storage_relpath AS archive_relpath, a.size_bytes AS archive_size,
                       a.sha256 AS archive_sha256
                FROM perfect_catalog.image_product_candidate AS c
                JOIN perfect_catalog.image_product_decision AS d
                  ON d.image_product_candidate_id=c.image_product_candidate_id
                JOIN perfect_catalog.image_archive_entry AS e
                  ON e.image_archive_entry_id=c.image_archive_entry_id
                JOIN perfect_catalog.image_archive_index AS i
                  ON i.image_archive_index_id=e.image_archive_index_id
                JOIN perfect_catalog.intake_submission AS s
                  ON s.intake_submission_id=i.intake_submission_id
                JOIN perfect_catalog.intake_asset AS a
                  ON a.intake_asset_id=s.intake_asset_id
                WHERE c.image_product_candidate_id=%s AND s.company_id=%s
                """,
                (candidate_id, company_id),
            )
            record = cursor.fetchone()
            if record is None:
                raise ValueError("No existe una decisión para el candidato solicitado.")
            if record["decision"] != "approved":
                raise PermissionError("Sólo se materializan candidatos aprobados.")
            if record["evidence_sha256"] != evidence_sha256 or record["candidate_evidence_sha256"] != evidence_sha256:
                raise PermissionError("El hash aprobado no coincide con el candidato.")
            cursor.execute(
                "SELECT approved_image_materialization_id, storage_relpath, content_sha256 FROM perfect_catalog.approved_image_materialization WHERE image_product_decision_id=%s",
                (record["image_product_decision_id"],),
            )
            existing = cursor.fetchone()
            if existing:
                return {"status": "already_materialized", **dict(existing)}

        archive_path = _confined(intake_root, record["archive_relpath"])
        if not archive_path.is_file() or archive_path.stat().st_size != record["archive_size"]:
            raise RuntimeError("El ZIP de cuarentena falta o cambió de tamaño.")
        if _sha256(archive_path) != record["archive_sha256"]:
            raise RuntimeError("El ZIP de cuarentena no coincide con su SHA-256.")
        storage_relpath = Path("objects") / str(record["content_sha256"])[:2] / f"{record['content_sha256']}{record['extension']}"
        destination = _confined(image_root, storage_relpath.as_posix())
        _copy_verified_member(
            archive_path, record["member_path"], str(record["content_sha256"]),
            int(record["uncompressed_size"]), str(record["crc32"]), destination,
        )
        materialization_id = uuid.uuid4()
        connection.execute(
            """
            INSERT INTO perfect_catalog.approved_image_materialization (
                approved_image_materialization_id, image_product_decision_id,
                image_product_candidate_id, image_archive_entry_id,
                product_template_id, product_variant_id, content_sha256,
                media_type, byte_size, storage_relpath, original_filename,
                materialized_by, reason, materialized_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (materialization_id, record["image_product_decision_id"], candidate_id,
             record["image_archive_entry_id"], record["product_template_id"],
             record["product_variant_id"], record["content_sha256"], record["media_type"],
             record["uncompressed_size"], storage_relpath.as_posix(), record["original_filename"],
             actor, reason, datetime.now(UTC)),
        )
    return {
        "status": "materialized", "approved_image_materialization_id": str(materialization_id),
        "storage_relpath": storage_relpath.as_posix(), "content_sha256": str(record["content_sha256"]),
    }


def materialize_approved_images_bulk(
    expected_count: int, intake_root: Path, image_root: Path,
    config: DatabaseConfig, password: str, *, actor: str, reason: str,
    company_id: uuid.UUID, max_items: int = 500,
) -> dict[str, Any]:
    """Materializa el conjunto exacto de aprobadas pendientes, verificando cada archivo."""
    actor, reason = _actor(actor), _reason(reason)
    if not 1 <= expected_count <= max_items:
        raise ValueError(f"expected_count debe estar entre 1 y {max_items}.")
    with psycopg.connect(**config.connection_kwargs(password), row_factory=dict_row) as connection:
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 6))",
            ("perfect_catalog.approved_image_materialization.bulk",),
        )
        rows = connection.execute(
            """
            SELECT c.image_product_candidate_id, c.evidence_sha256
            FROM perfect_catalog.image_product_candidate AS c
            JOIN perfect_catalog.image_archive_entry AS e
              ON e.image_archive_entry_id=c.image_archive_entry_id
            JOIN perfect_catalog.image_archive_index AS i
              ON i.image_archive_index_id=e.image_archive_index_id
            JOIN perfect_catalog.intake_submission AS s
              ON s.intake_submission_id=i.intake_submission_id
            JOIN perfect_catalog.image_product_decision AS d
              ON d.image_product_candidate_id=c.image_product_candidate_id
             AND d.decision='approved'
            LEFT JOIN perfect_catalog.approved_image_materialization AS m
              ON m.image_product_candidate_id=c.image_product_candidate_id
            WHERE m.approved_image_materialization_id IS NULL AND s.company_id=%s
            ORDER BY d.decided_at, c.image_product_candidate_id
            LIMIT %s
            """,
            (company_id, max_items + 1),
        ).fetchall()
    if len(rows) != expected_count:
        raise PermissionError("La cantidad aprobada sin materializar cambió; recarga la página.")
    completed = 0
    for row in rows:
        result = materialize_approved_image(
            row["image_product_candidate_id"], str(row["evidence_sha256"]),
            intake_root, image_root, config, password,
            actor=actor, reason=reason, company_id=company_id,
        )
        if result["status"] in {"materialized", "already_materialized"}:
            completed += 1
    return {"status": "bulk_materialized", "count": completed}
