from __future__ import annotations

import hashlib
import re
import unicodedata
import uuid
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .canonical import canonical_sha256
from .config import DatabaseConfig
from .intake import IMAGE_EXTENSIONS, _inspect_archive
from .intake_promotion import _actor, _confined, _reason, _sha256


IMAGE_INDEX_ALGORITHM = "quarantined-image-index-v1"
_MEDIA_TYPES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".webp": "image/webp", ".tif": "image/tiff", ".tiff": "image/tiff",
    ".bmp": "image/bmp", ".gif": "image/gif", ".heic": "image/heic",
    ".heif": "image/heif", ".dng": "image/x-adobe-dng",
}


def normalize_image_key(filename: str) -> str:
    stem = Path(filename).stem
    text = unicodedata.normalize("NFKD", stem)
    text = "".join(char for char in text if not unicodedata.combining(char)).upper()
    return re.sub(r"[^A-Z0-9]+", "-", text).strip("-")


_VARIANT_SUFFIX_RE = re.compile(r"^(.+)-([2-9]|[1-9]\d)$")


def split_variant_suffix(key: str) -> tuple[str, int | None]:
    """`REF-1234-2` -> (`REF-1234`, 2): a normalized key ending in `-<N>` (2 <= N <= 99) names
    an extra photo of the base reference, not a different product. `REF-1234` (no suffix) is
    always the main photo; there is no `-1` variant by convention, only `-2`, `-3`, etc.

    The suffix is capped at two digits on purpose: a real reference's own trailing digits
    (e.g. `REF-1234`, four digits) must never be misread as a huge variant index. This is
    only a heuristic fallback — callers must always try an exact, unsplit match against real
    approved references first, and only fall back to this split when that direct match finds
    nothing, so a reference that genuinely ends in `-2`..`-99` is never shadowed by it.
    """
    match = _VARIANT_SUFFIX_RE.fullmatch(key)
    if not match:
        return key, None
    return match.group(1), int(match.group(2))


def inspect_image_archive(path: Path) -> dict[str, Any]:
    members, archive_report = _inspect_archive(Path(path))
    image_members = [(info, member) for info, member in members if member.suffix.lower() in IMAGE_EXTENSIONS]
    if not image_members:
        raise ValueError("El ZIP no contiene imágenes admitidas.")
    keys = [normalize_image_key(member.name) for _, member in image_members]
    if any(not key for key in keys):
        raise ValueError("Una imagen no produce una clave de búsqueda utilizable.")
    counts = Counter(keys)
    entries: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as archive:
        for order, ((info, member), key) in enumerate(zip(image_members, keys, strict=True), start=1):
            digest = hashlib.sha256()
            with archive.open(info, "r") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
            entries.append({
                "entry_order": order,
                "member_path": member.as_posix(),
                "original_filename": member.name,
                "extension": member.suffix.lower(),
                "media_type": _MEDIA_TYPES.get(member.suffix.lower(), "application/octet-stream"),
                "uncompressed_size": info.file_size,
                "compressed_size": info.compress_size,
                "crc32": f"{info.CRC:08x}",
                "content_sha256": digest.hexdigest(),
                "lookup_key": key,
                "match_status": "ambiguous" if counts[key] > 1 else "unmatched",
                "conflict_count": counts[key],
            })
    return {
        "algorithm": IMAGE_INDEX_ALGORITHM,
        "archive": archive_report,
        "image_count": len(entries),
        "ambiguous_entries": sum(entry["match_status"] == "ambiguous" for entry in entries),
        "entries": entries,
    }


def build_image_archive_index(
    submission_id: uuid.UUID,
    intake_root: Path,
    config: DatabaseConfig,
    password: str,
    *,
    actor: str,
    reason: str,
) -> dict[str, Any]:
    actor, reason = _actor(actor), _reason(reason)
    root = Path(intake_root).resolve()
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 1))", (str(submission_id),))
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                "SELECT image_archive_index_id, index_sha256, image_count, ambiguous_count FROM perfect_catalog.image_archive_index WHERE intake_submission_id=%s",
                (submission_id,),
            )
            existing = cursor.fetchone()
            if existing:
                return {"status": "already_indexed", **{key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(existing).items()}}
            cursor.execute(
                """
                SELECT s.intake_asset_id, s.intake_kind, s.validation_status, s.size_bytes,
                       s.sha256, a.storage_relpath
                FROM perfect_catalog.intake_submission AS s
                LEFT JOIN perfect_catalog.intake_asset AS a ON a.intake_asset_id=s.intake_asset_id
                WHERE s.intake_submission_id=%s
                """,
                (submission_id,),
            )
            submission = cursor.fetchone()
        if submission is None:
            raise ValueError("No existe el ingreso solicitado.")
        if submission["intake_kind"] != "image_archive" or submission["validation_status"] != "quarantined":
            raise PermissionError("Sólo se indexan paquetes de imágenes aceptados y en cuarentena.")
        source = _confined(root, submission["storage_relpath"])
        if not source.is_file() or source.stat().st_size != submission["size_bytes"]:
            raise RuntimeError("El ZIP en cuarentena falta o no coincide con su tamaño registrado.")
        if _sha256(source) != submission["sha256"]:
            raise RuntimeError("El ZIP en cuarentena no coincide con su SHA-256 registrado.")
        report = inspect_image_archive(source)
        if _sha256(source) != submission["sha256"]:
            raise RuntimeError("El ZIP cambió durante la indexación; no se guardó evidencia.")
        index_id = uuid.uuid4()
        evidence = {
            "algorithm": IMAGE_INDEX_ALGORITHM,
            "source_sha256": submission["sha256"],
            "entries": report["entries"],
        }
        index_sha256 = canonical_sha256(evidence)
        now = datetime.now(UTC)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO perfect_catalog.image_archive_index (
                    image_archive_index_id, intake_submission_id, intake_asset_id,
                    source_sha256, algorithm, index_sha256, image_count, ambiguous_count,
                    report, indexed_by, reason, indexed_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (index_id, submission_id, submission["intake_asset_id"], submission["sha256"],
                 IMAGE_INDEX_ALGORITHM, index_sha256, report["image_count"], report["ambiguous_entries"],
                 Jsonb({key: value for key, value in report.items() if key != "entries"}), actor, reason, now),
            )
            for entry in report["entries"]:
                cursor.execute(
                    """
                    INSERT INTO perfect_catalog.image_archive_entry (
                        image_archive_entry_id, image_archive_index_id, entry_order,
                        member_path, original_filename, extension, media_type,
                        uncompressed_size, compressed_size, crc32, content_sha256,
                        lookup_key, match_status, conflict_count, indexed_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (uuid.uuid4(), index_id, entry["entry_order"], entry["member_path"],
                     entry["original_filename"], entry["extension"], entry["media_type"],
                     entry["uncompressed_size"], entry["compressed_size"], entry["crc32"],
                     entry["content_sha256"], entry["lookup_key"], entry["match_status"],
                     entry["conflict_count"], now),
                )
        connection.commit()
        return {"status": "indexed", "image_archive_index_id": str(index_id), "index_sha256": index_sha256, **report}
