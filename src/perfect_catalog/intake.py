from __future__ import annotations

import hashlib
import os
import re
import stat
import tempfile
import threading
import unicodedata
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Protocol

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .config import DatabaseConfig


INTAKE_ALGORITHM = "secure-intake-envelope-v1"
INTAKE_KINDS = {
    "odoo_data": {
        "label": "Datos de Odoo",
        "extensions": frozenset({".xlsx", ".csv", ".tsv"}),
        "max_bytes": 128 * 1024 * 1024,
    },
    "image_archive": {
        "label": "Paquete de imágenes",
        "extensions": frozenset({".zip"}),
        "max_bytes": 2 * 1024 * 1024 * 1024,
    },
    "manual_pdf": {
        "label": "Manual o especificación PDF",
        "extensions": frozenset({".pdf"}),
        "max_bytes": 256 * 1024 * 1024,
    },
    "indesign_package": {
        "label": "Paquete de InDesign",
        "extensions": frozenset({".zip"}),
        "max_bytes": 2 * 1024 * 1024 * 1024,
    },
}
INTAKE_STATUSES = frozenset({"all", "quarantined", "rejected"})
MAX_UPLOAD_REQUEST_BYTES = max(
    int(config["max_bytes"]) for config in INTAKE_KINDS.values()
) + 64 * 1024
MAX_ARCHIVE_ENTRIES = 50_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 50 * 1024 * 1024 * 1024
MAX_ARCHIVE_RATIO = 200
IMAGE_EXTENSIONS = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".tif",
        ".tiff",
        ".bmp",
        ".gif",
        ".heic",
        ".heif",
        ".raw",
        ".nef",
        ".cr2",
        ".arw",
        ".dng",
    }
)
IMAGE_SIDECAR_EXTENSIONS = frozenset({".xmp", ".icc", ".icm", ".csv", ".txt"})
BLOCKED_PACKAGE_EXTENSIONS = frozenset(
    {".exe", ".dll", ".com", ".bat", ".cmd", ".ps1", ".vbs", ".msi", ".scr"}
)
INDESIGN_EXTENSIONS = frozenset({".indd", ".idml", ".indt"})
WINDOWS_RESERVED_NAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)


class IntakePersistence(Protocol):
    def record_intake(self, record: dict[str, Any]) -> dict[str, Any]: ...

    def intake_submissions(
        self,
        *,
        kind: str = "all",
        status: str = "all",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class IntakeValidation:
    accepted: bool
    detected_media_type: str
    report: dict[str, Any]


def intake_kind_options() -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "value": kind,
            "label": config["label"],
            "accept": ",".join(sorted(config["extensions"])),
            "max_bytes": config["max_bytes"],
        }
        for kind, config in INTAKE_KINDS.items()
    )


def _safe_filename(value: str | None) -> tuple[str, str]:
    name = unicodedata.normalize("NFKC", str(value or "")).strip()
    if not name or len(name) > 240:
        raise ValueError("El nombre del archivo debe contener entre 1 y 240 caracteres.")
    if any(character in name for character in ("/", "\\", "\x00")):
        raise ValueError("El nombre del archivo no puede contener rutas.")
    if name in {".", ".."} or name.endswith((".", " ")):
        raise ValueError("El nombre del archivo no es válido para almacenamiento local.")
    path = Path(name)
    extension = path.suffix.lower()
    if not extension or not re.fullmatch(r"\.[a-z0-9]{1,12}", extension):
        raise ValueError("El archivo debe tener una extensión simple reconocible.")
    if path.stem.upper() in WINDOWS_RESERVED_NAMES:
        raise ValueError("El nombre del archivo está reservado por Windows.")
    return name, extension


def _require_kind(kind: str) -> dict[str, Any]:
    normalized = str(kind or "").strip().lower()
    if normalized not in INTAKE_KINDS:
        raise ValueError("El tipo de ingreso no está permitido.")
    return INTAKE_KINDS[normalized]


def _require_reason(reason: str) -> str:
    normalized = str(reason or "").strip()
    if not 4 <= len(normalized) <= 500:
        raise ValueError("El motivo debe contener entre 4 y 500 caracteres.")
    return normalized


def _require_list_filters(
    kind: str, status: str, limit: int, offset: int
) -> tuple[str, str]:
    if not 1 <= limit <= 500:
        raise ValueError("limit debe estar entre 1 y 500.")
    if offset < 0:
        raise ValueError("offset no puede ser negativo.")
    kind = str(kind or "all").strip().lower()
    status = str(status or "all").strip().lower()
    if kind != "all" and kind not in INTAKE_KINDS:
        raise ValueError("Filtro de tipo de ingreso inválido.")
    if status not in INTAKE_STATUSES:
        raise ValueError("Filtro de estado de ingreso inválido.")
    return kind, status


def _archive_member_name(raw_name: str) -> PurePosixPath:
    normalized = raw_name.replace("\\", "/")
    if not normalized or "\x00" in normalized or normalized.startswith(("/", "//")):
        raise ValueError("El ZIP contiene una ruta absoluta o vacía.")
    if re.match(r"^[a-zA-Z]:", normalized):
        raise ValueError("El ZIP contiene una ruta absoluta de Windows.")
    path = PurePosixPath(normalized)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("El ZIP contiene una ruta no normalizada.")
    if len(normalized) > 500:
        raise ValueError("El ZIP contiene una ruta demasiado larga.")
    for part in path.parts:
        if (
            len(part) > 240
            or part.endswith((".", " "))
            or any(character in part for character in '<>:"|?*')
            or Path(part).stem.upper() in WINDOWS_RESERVED_NAMES
        ):
            raise ValueError("El ZIP contiene un nombre incompatible con almacenamiento seguro.")
    return path


def _inspect_archive(
    path: Path,
) -> tuple[list[tuple[zipfile.ZipInfo, PurePosixPath]], dict[str, Any]]:
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if not infos or len(infos) > MAX_ARCHIVE_ENTRIES:
                raise ValueError(
                    f"El ZIP debe contener entre 1 y {MAX_ARCHIVE_ENTRIES:,} entradas."
                )
            members: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
            names: set[str] = set()
            total_size = 0
            total_compressed = 0
            for info in infos:
                member = _archive_member_name(info.filename)
                comparable = member.as_posix().casefold()
                if comparable in names:
                    raise ValueError("El ZIP contiene nombres duplicados al normalizar.")
                names.add(comparable)
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise ValueError("El ZIP contiene enlaces simbólicos.")
                if info.flag_bits & 0x1:
                    raise ValueError("El ZIP contiene entradas cifradas.")
                if not info.is_dir():
                    total_size += info.file_size
                    total_compressed += info.compress_size
                    members.append((info, member))
            if not members:
                raise ValueError("El ZIP no contiene archivos.")
            if total_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                raise ValueError("El ZIP supera el límite descomprimido de 50 GiB.")
            ratio = total_size / max(total_compressed, 1)
            if total_size > 10 * 1024 * 1024 and ratio > MAX_ARCHIVE_RATIO:
                raise ValueError(
                    "El ZIP tiene una relación de compresión potencialmente peligrosa."
                )
            return members, {
                "archive_entries": len(infos),
                "archive_files": len(members),
                "uncompressed_bytes": total_size,
                "compression_ratio": round(ratio, 2),
            }
    except zipfile.BadZipFile as exc:
        raise ValueError("El archivo no es un ZIP válido.") from exc


def _validate_odoo(path: Path, extension: str) -> IntakeValidation:
    if extension == ".xlsx":
        members, archive_report = _inspect_archive(path)
        names = {member.as_posix() for _, member in members}
        required = {"[Content_Types].xml", "xl/workbook.xml"}
        if not required.issubset(names):
            raise ValueError("El XLSX no contiene la estructura mínima de un libro Excel.")
        return IntakeValidation(
            True,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            {**archive_report, "workbook_structure": "present"},
        )
    with path.open("rb") as handle:
        sample = handle.read(1024 * 1024)
    utf16_bom = sample.startswith((b"\xff\xfe", b"\xfe\xff"))
    if b"\x00" in sample and not utf16_bom:
        raise ValueError("El archivo tabular contiene bytes nulos y no parece texto.")
    encoding = None
    candidates = ("utf-16",) if utf16_bom else ("utf-8-sig", "cp1252")
    for candidate in candidates:
        try:
            decoded = sample.decode(candidate)
            encoding = candidate
            break
        except UnicodeDecodeError:
            continue
    if encoding is None or not decoded.strip():
        raise ValueError("El archivo tabular está vacío o usa una codificación no admitida.")
    delimiter = "," if extension == ".csv" else "\t"
    if delimiter not in decoded.splitlines()[0]:
        raise ValueError("La primera fila no contiene el separador esperado.")
    return IntakeValidation(
        True,
        "text/csv" if extension == ".csv" else "text/tab-separated-values",
        {"encoding": encoding, "delimiter": "comma" if delimiter == "," else "tab"},
    )


def _validate_image_archive(path: Path) -> IntakeValidation:
    members, report = _inspect_archive(path)
    ignored = 0
    images = 0
    sidecars = 0
    unsupported: list[str] = []
    for _, member in members:
        member_name = member.name
        if "__MACOSX" in member.parts or member_name == ".DS_Store":
            ignored += 1
            continue
        if member.suffix.lower() in IMAGE_EXTENSIONS:
            images += 1
        elif member.suffix.lower() in IMAGE_SIDECAR_EXTENSIONS:
            sidecars += 1
        elif len(unsupported) < 5:
            unsupported.append(member.as_posix())
    if images == 0:
        raise ValueError("El ZIP no contiene imágenes con extensiones admitidas.")
    if unsupported:
        raise ValueError(
            "El ZIP de imágenes contiene archivos no admitidos: " + ", ".join(unsupported)
        )
    return IntakeValidation(
        True,
        "application/zip",
        {
            **report,
            "image_files": images,
            "sidecar_files": sidecars,
            "ignored_metadata_files": ignored,
        },
    )


def _validate_indesign_archive(path: Path) -> IntakeValidation:
    members, report = _inspect_archive(path)
    documents = 0
    blocked: list[str] = []
    for _, member in members:
        suffix = member.suffix.lower()
        if suffix in INDESIGN_EXTENSIONS:
            documents += 1
        if suffix in BLOCKED_PACKAGE_EXTENSIONS and len(blocked) < 5:
            blocked.append(member.as_posix())
    if blocked:
        raise ValueError("El paquete contiene ejecutables bloqueados: " + ", ".join(blocked))
    if documents == 0:
        raise ValueError("El paquete no contiene archivos INDD, IDML o INDT.")
    return IntakeValidation(
        True,
        "application/zip",
        {**report, "indesign_documents": documents},
    )


def validate_intake(path: Path, kind: str, extension: str) -> IntakeValidation:
    try:
        if kind == "odoo_data":
            result = _validate_odoo(path, extension)
        elif kind == "image_archive":
            result = _validate_image_archive(path)
        elif kind == "manual_pdf":
            with path.open("rb") as handle:
                if handle.read(5) != b"%PDF-":
                    raise ValueError("El archivo no contiene una cabecera PDF válida.")
            result = IntakeValidation(True, "application/pdf", {"pdf_header": "present"})
        elif kind == "indesign_package":
            result = _validate_indesign_archive(path)
        else:  # protected by _require_kind, retained for direct callers
            raise ValueError("El tipo de ingreso no está permitido.")
        return IntakeValidation(
            result.accepted,
            result.detected_media_type,
            {"algorithm": INTAKE_ALGORITHM, **result.report, "errors": []},
        )
    except (OSError, ValueError) as exc:
        return IntakeValidation(
            False,
            "application/octet-stream",
            {"algorithm": INTAKE_ALGORITHM, "errors": [str(exc)]},
        )


class SecureIntakeService:
    def __init__(self, root: Path, persistence: IntakePersistence) -> None:
        self.root = Path(root).resolve()
        self.persistence = persistence
        self._lock = threading.Lock()

    def list(
        self,
        *,
        kind: str = "all",
        status: str = "all",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        kind, status = _require_list_filters(kind, status, limit, offset)
        return self.persistence.intake_submissions(
            kind=kind, status=status, limit=limit, offset=offset
        )

    def submit(
        self,
        source: BinaryIO,
        *,
        filename: str | None,
        claimed_media_type: str | None,
        kind: str,
        actor: str,
        reason: str,
    ) -> dict[str, Any]:
        config = _require_kind(kind)
        kind = str(kind).strip().lower()
        filename, extension = _safe_filename(filename)
        if extension not in config["extensions"]:
            allowed = ", ".join(sorted(config["extensions"]))
            raise ValueError(f"{config['label']} admite únicamente: {allowed}.")
        actor = str(actor or "").strip()
        if not actor or len(actor) > 120:
            raise ValueError("El actor de ingreso no es válido.")
        reason = _require_reason(reason)
        claimed_media_type = str(claimed_media_type or "").strip() or None
        if claimed_media_type is not None and len(claimed_media_type) > 120:
            raise ValueError("El tipo de contenido declarado es demasiado largo.")

        temporary_dir = self.root / ".tmp"
        temporary_dir.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=temporary_dir, prefix="intake-", suffix=".upload", delete=False
            ) as target:
                temporary_path = Path(target.name)
                digest = hashlib.sha256()
                size = 0
                source.seek(0)
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > int(config["max_bytes"]):
                        max_mebibytes = int(config["max_bytes"]) // (1024 * 1024)
                        raise ValueError(
                            f"El archivo supera el límite de {max_mebibytes:,} MiB."
                        )
                    digest.update(chunk)
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
            if size == 0:
                raise ValueError("El archivo está vacío.")
            sha256 = digest.hexdigest()
            validation = validate_intake(temporary_path, kind, extension)
            record = {
                "intake_submission_id": uuid.uuid4(),
                "intake_kind": kind,
                "original_name": filename,
                "extension": extension,
                "claimed_media_type": claimed_media_type,
                "detected_media_type": validation.detected_media_type,
                "size_bytes": size,
                "sha256": sha256,
                "validation_status": "quarantined" if validation.accepted else "rejected",
                "validation_report": validation.report,
                "submitted_by": actor,
                "reason": reason,
                "submitted_at": datetime.now(UTC),
                "storage_relpath": f"quarantine/objects/{sha256[:2]}/{sha256}",
            }
            if not validation.accepted:
                return self.persistence.record_intake(record)

            destination = self.root.joinpath(*PurePosixPath(record["storage_relpath"]).parts)
            newly_stored = False
            with self._lock:
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    if destination.stat().st_size != size:
                        raise RuntimeError("El objeto existente no coincide con su hash y tamaño.")
                else:
                    os.replace(temporary_path, destination)
                    temporary_path = None
                    newly_stored = True
                try:
                    return self.persistence.record_intake(record)
                except Exception:
                    if newly_stored and destination.exists():
                        destination.unlink()
                    raise
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()


def _record_intake_in_connection(
    connection: Connection[Any], record: dict[str, Any]
) -> dict[str, Any]:
    asset_id: uuid.UUID | None = None
    duplicate_content = False
    if record["validation_status"] == "quarantined":
        proposed_asset_id = uuid.uuid4()
        inserted = connection.execute(
            """
            INSERT INTO perfect_catalog.intake_asset (
                intake_asset_id, sha256, size_bytes, detected_media_type,
                storage_relpath, received_at, received_by
            ) VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (sha256) DO NOTHING
            RETURNING intake_asset_id
            """,
            (
                proposed_asset_id,
                record["sha256"],
                record["size_bytes"],
                record["detected_media_type"],
                record["storage_relpath"],
                record["submitted_at"],
                record["submitted_by"],
            ),
        ).fetchone()
        if inserted is not None:
            asset_id = inserted[0]
        else:
            duplicate_content = True
            existing = connection.execute(
                """
                SELECT intake_asset_id, size_bytes, detected_media_type, storage_relpath
                FROM perfect_catalog.intake_asset WHERE sha256=%s
                """,
                (record["sha256"],),
            ).fetchone()
            if existing is None or (
                int(existing[1]), existing[2], existing[3]
            ) != (
                int(record["size_bytes"]),
                record["detected_media_type"],
                record["storage_relpath"],
            ):
                raise RuntimeError("El objeto duplicado no coincide con sus metadatos inmutables.")
            asset_id = existing[0]
    connection.execute(
        """
        INSERT INTO perfect_catalog.intake_submission (
            intake_submission_id, intake_asset_id, intake_kind, original_name,
            extension, claimed_media_type, detected_media_type, size_bytes,
            sha256, validation_status, duplicate_content, validation_report,
            submitted_by, reason, submitted_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            record["intake_submission_id"],
            asset_id,
            record["intake_kind"],
            record["original_name"],
            record["extension"],
            record["claimed_media_type"],
            record["detected_media_type"],
            record["size_bytes"],
            record["sha256"],
            record["validation_status"],
            duplicate_content,
            Jsonb(record["validation_report"]),
            record["submitted_by"],
            record["reason"],
            record["submitted_at"],
        ),
    )
    return {
        **record,
        "intake_submission_id": str(record["intake_submission_id"]),
        "intake_asset_id": str(asset_id) if asset_id is not None else None,
        "duplicate_content": duplicate_content,
    }


def record_intake(
    config: DatabaseConfig, password: str, record: dict[str, Any]
) -> dict[str, Any]:
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        return _record_intake_in_connection(connection, record)


def _list_intake_submissions_in_connection(
    connection: Connection[Any],
    *,
    kind: str = "all",
    status: str = "all",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    kind, status = _require_list_filters(kind, status, limit, offset)
    clauses: list[str] = []
    params: list[Any] = []
    if kind != "all":
        clauses.append("s.intake_kind=%s")
        params.append(kind)
    if status != "all":
        clauses.append("s.validation_status=%s")
        params.append(status)
    where_sql = "WHERE " + " AND ".join(clauses) if clauses else ""
    query = f"""
        SELECT s.intake_submission_id, s.intake_asset_id, s.intake_kind,
               s.original_name, s.extension, s.claimed_media_type,
               s.detected_media_type, s.size_bytes, s.sha256,
               s.validation_status, s.duplicate_content,
               s.validation_report, s.submitted_by, s.reason, s.submitted_at,
               p.intake_promotion_id, p.import_plan_id, p.promoted_at, p.promoted_by,
               x.image_archive_index_id, x.index_sha256 AS image_index_sha256,
               x.image_count, x.ambiguous_count, x.indexed_at, x.indexed_by,
               count(*) OVER () AS filtered_count
        FROM perfect_catalog.intake_submission AS s
        LEFT JOIN perfect_catalog.intake_promotion AS p
          ON p.intake_submission_id=s.intake_submission_id
        LEFT JOIN perfect_catalog.image_archive_index AS x
          ON x.intake_submission_id=s.intake_submission_id
        {where_sql}
        ORDER BY s.submitted_at DESC, s.intake_submission_id DESC
        LIMIT %s OFFSET %s
    """
    page_params = [*params, limit, offset]
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query, page_params)
        rows = [dict(row) for row in cursor.fetchall()]
        if rows:
            filtered_count = int(rows[0].pop("filtered_count"))
            for row in rows[1:]:
                row.pop("filtered_count", None)
        else:
            count_sql = (
                "SELECT count(*) AS filtered_count "
                f"FROM perfect_catalog.intake_submission AS s {where_sql}"
            )
            cursor.execute(count_sql, params)
            filtered_count = int(cursor.fetchone()["filtered_count"])
    return {
        "items": rows,
        "filtered_count": filtered_count,
        "kind": kind,
        "status": status,
        "limit": limit,
        "offset": offset,
    }


def list_intake_submissions(
    config: DatabaseConfig,
    password: str,
    *,
    kind: str = "all",
    status: str = "all",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    with psycopg.connect(**config.connection_kwargs(password)) as connection:
        return _list_intake_submissions_in_connection(
            connection,
            kind=kind,
            status=status,
            limit=limit,
            offset=offset,
        )
