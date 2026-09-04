from __future__ import annotations

import hashlib
import io
import os
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from PIL import Image as PILImage, ImageOps
from psycopg.rows import dict_row

from .config import DatabaseConfig
from .intake_promotion import _actor, _confined, _reason, _sha256

MAX_CANDIDATE_PREVIEW_SIDE_PX = 320


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


def _thumbnail_jpeg(content: bytes, *, max_side_px: int = MAX_CANDIDATE_PREVIEW_SIDE_PX) -> bytes:
    """Miniatura pequeña para revisar de un vistazo; nunca se guarda ni se usa como evidencia."""
    with PILImage.open(io.BytesIO(content)) as source:
        image = ImageOps.exif_transpose(source)
        image.thumbnail((max_side_px, max_side_px), PILImage.Resampling.LANCZOS)
        if image.mode not in {"RGB", "L"}:
            background = PILImage.new("RGB", image.size, "white")
            if "A" in image.getbands():
                background.paste(image, mask=image.getchannel("A"))
            else:
                background.paste(image.convert("RGB"))
            image = background
        elif image.mode == "L":
            image = image.convert("RGB")
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=78, optimize=True)
    return output.getvalue()


def _verified_thumbnail_from_archive(intake_root: Path, record: dict[str, Any]) -> bytes:
    """Cola compartida: verifica el ZIP en cuarentena y su entrada exactamente igual que al
    materializar (tamaño, SHA-256, CRC), y devuelve una miniatura — sin copiar ni aprobar nada."""
    archive_path = _confined(intake_root, record["archive_relpath"])
    if not archive_path.is_file() or archive_path.stat().st_size != record["archive_size"]:
        raise RuntimeError("El ZIP de cuarentena falta o cambió de tamaño.")
    if _sha256(archive_path) != record["archive_sha256"]:
        raise RuntimeError("El ZIP de cuarentena no coincide con su SHA-256.")
    with zipfile.ZipFile(archive_path) as archive:
        try:
            info = archive.getinfo(record["member_path"])
        except KeyError as exc:
            raise RuntimeError("La entrada indexada ya no existe dentro del ZIP.") from exc
        if info.file_size != record["uncompressed_size"] or f"{info.CRC:08x}" != record["crc32"]:
            raise RuntimeError("Tamaño o CRC de la entrada no coincide con el índice.")
        content = archive.read(info)
    if hashlib.sha256(content).hexdigest() != record["content_sha256"]:
        raise RuntimeError("Los bytes leídos no coinciden con el SHA-256 indexado.")
    return _thumbnail_jpeg(content)


def resolve_image_candidate_preview(
    candidate_id: uuid.UUID, intake_root: Path,
    config: DatabaseConfig, password: str, *, company_id: uuid.UUID,
) -> bytes:
    """Miniatura de solo lectura leída directamente del ZIP en cuarentena, verificada por
    SHA-256/CRC exactamente igual que al materializar — pero sin copiar ni aprobar nada. Deja
    que el operador vea la foto real antes de decidir, en vez de solo un nombre de archivo."""
    intake_root = Path(intake_root).resolve()
    with psycopg.connect(**config.connection_kwargs(password), row_factory=dict_row) as connection:
        record = connection.execute(
            """
            SELECT e.member_path, e.uncompressed_size, e.crc32, e.content_sha256,
                   a.storage_relpath AS archive_relpath, a.size_bytes AS archive_size,
                   a.sha256 AS archive_sha256
            FROM perfect_catalog.image_product_candidate AS c
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
        ).fetchone()
    if record is None:
        raise ValueError("No existe el candidato de imagen solicitado.")
    return _verified_thumbnail_from_archive(intake_root, record)


def resolve_image_entry_preview(
    entry_id: uuid.UUID, intake_root: Path,
    config: DatabaseConfig, password: str, *, company_id: uuid.UUID,
) -> bytes:
    """Miniatura de solo lectura de cualquier entrada indexada, tenga o no un candidato de
    coincidencia — para revisar fotos sin match o ambiguas antes de decidir qué hacer con ellas."""
    intake_root = Path(intake_root).resolve()
    with psycopg.connect(**config.connection_kwargs(password), row_factory=dict_row) as connection:
        record = connection.execute(
            """
            SELECT e.member_path, e.uncompressed_size, e.crc32, e.content_sha256,
                   a.storage_relpath AS archive_relpath, a.size_bytes AS archive_size,
                   a.sha256 AS archive_sha256
            FROM perfect_catalog.image_archive_entry AS e
            JOIN perfect_catalog.image_archive_index AS i
              ON i.image_archive_index_id=e.image_archive_index_id
            JOIN perfect_catalog.intake_submission AS s
              ON s.intake_submission_id=i.intake_submission_id
            JOIN perfect_catalog.intake_asset AS a
              ON a.intake_asset_id=s.intake_asset_id
            WHERE e.image_archive_entry_id=%s AND s.company_id=%s
            """,
            (entry_id, company_id),
        ).fetchone()
    if record is None:
        raise ValueError("No existe la entrada de imagen solicitada.")
    return _verified_thumbnail_from_archive(intake_root, record)


def materialize_approved_image(
    candidate_id: uuid.UUID, evidence_sha256: str,
    intake_root: Path, image_root: Path,
    config: DatabaseConfig, password: str,
    *, actor: str, reason: str, company_id: uuid.UUID,
) -> dict[str, Any]:
    """Publica la copia verificada de un candidato aprobado.

    Un candidato sin `variant_index` es la foto principal del producto (tabla
    `approved_image_materialization`, una por producto). Un candidato con `variant_index`
    viene de un archivo con sufijo (`REF-1234-2.jpg`) y es una foto adicional de la galería
    (tabla `approved_image_variant`, varias por producto). El llamador no necesita saber cuál
    es: esta función decide según lo que ya quedó registrado al generar el candidato.
    """
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
                       c.image_product_candidate_id, c.evidence_sha256, c.variant_index,
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
            is_variant = record["variant_index"] is not None
            existing_table = "approved_image_variant" if is_variant else "approved_image_materialization"
            existing_id_column = "approved_image_variant_id" if is_variant else "approved_image_materialization_id"
            cursor.execute(
                f"SELECT {existing_id_column}, storage_relpath, content_sha256 "
                f"FROM perfect_catalog.{existing_table} WHERE image_product_decision_id=%s",
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
        if is_variant:
            variant_id = uuid.uuid4()
            connection.execute(
                """
                INSERT INTO perfect_catalog.approved_image_variant (
                    approved_image_variant_id, image_product_decision_id,
                    image_product_candidate_id, image_archive_entry_id,
                    product_template_id, product_variant_id, variant_index, content_sha256,
                    media_type, byte_size, storage_relpath, original_filename,
                    materialized_by, reason, materialized_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (variant_id, record["image_product_decision_id"], candidate_id,
                 record["image_archive_entry_id"], record["product_template_id"],
                 record["product_variant_id"], record["variant_index"], record["content_sha256"],
                 record["media_type"], record["uncompressed_size"], storage_relpath.as_posix(),
                 record["original_filename"], actor, reason, datetime.now(UTC)),
            )
            return {
                "status": "materialized", "approved_image_variant_id": str(variant_id),
                "variant_index": record["variant_index"],
                "storage_relpath": storage_relpath.as_posix(), "content_sha256": str(record["content_sha256"]),
            }
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
            LEFT JOIN perfect_catalog.approved_image_variant AS v
              ON v.image_product_candidate_id=c.image_product_candidate_id
            WHERE s.company_id=%s
              AND ((c.variant_index IS NULL AND m.approved_image_materialization_id IS NULL)
                   OR (c.variant_index IS NOT NULL AND v.approved_image_variant_id IS NULL))
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
