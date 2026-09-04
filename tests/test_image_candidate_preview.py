from __future__ import annotations

import hashlib
import tempfile
import unittest
import uuid
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from perfect_catalog.approved_image_materialization import resolve_image_candidate_preview
from perfect_catalog.config import DatabaseConfig


PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
    "53de0000000c4944415408d763f8cfc0c0c0040007feff5f0e15d90000000049454e44ae426082"
)


class ImageCandidatePreviewTests(unittest.TestCase):
    """La miniatura de un candidato debe leerse en solo lectura, verificada por SHA-256/CRC
    como al materializar, pero sin copiar ni marcar nada como aprobado."""

    def _connection_mock(self, record) -> tuple[Mock, Mock]:
        connection = Mock()
        connection.execute.return_value.fetchone.return_value = record
        connection_context = Mock()
        connection_context.__enter__ = Mock(return_value=connection)
        connection_context.__exit__ = Mock(return_value=False)
        return connection, connection_context

    def _record_for(self, archive_path: Path, member_path: str, content: bytes) -> dict:
        with zipfile.ZipFile(archive_path) as archive:
            info = archive.getinfo(member_path)
        return {
            "member_path": member_path,
            "uncompressed_size": info.file_size,
            "crc32": f"{info.CRC:08x}",
            "content_sha256": hashlib.sha256(content).hexdigest(),
            "archive_relpath": "archive.zip",
            "archive_size": archive_path.stat().st_size,
            "archive_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        }

    def test_returns_a_verified_jpeg_thumbnail_without_writing_anything(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake_root = root / "intake"
            intake_root.mkdir()
            archive_path = intake_root / "archive.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("fotos/NK-001.png", PNG_BYTES)
            record = self._record_for(archive_path, "fotos/NK-001.png", PNG_BYTES)
            connection, connection_context = self._connection_mock(record)
            with patch("perfect_catalog.approved_image_materialization.psycopg.connect", return_value=connection_context):
                preview = resolve_image_candidate_preview(
                    uuid.uuid4(), intake_root, DatabaseConfig(), "secret", company_id=uuid.uuid4(),
                )
            self.assertTrue(preview.startswith(b"\xff\xd8"), "el resultado debe ser un JPEG re-codificado")
            self.assertEqual(sorted(intake_root.iterdir()), [archive_path])

    def test_rejects_when_the_zip_entry_no_longer_matches_its_indexed_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake_root = root / "intake"
            intake_root.mkdir()
            archive_path = intake_root / "archive.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("fotos/NK-001.png", PNG_BYTES)
            record = self._record_for(archive_path, "fotos/NK-001.png", PNG_BYTES)
            record["content_sha256"] = "0" * 64
            connection, connection_context = self._connection_mock(record)
            with patch("perfect_catalog.approved_image_materialization.psycopg.connect", return_value=connection_context):
                with self.assertRaisesRegex(RuntimeError, "SHA-256"):
                    resolve_image_candidate_preview(
                        uuid.uuid4(), intake_root, DatabaseConfig(), "secret", company_id=uuid.uuid4(),
                    )

    def test_rejects_an_unknown_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            intake_root = Path(temporary)
            connection, connection_context = self._connection_mock(None)
            with patch("perfect_catalog.approved_image_materialization.psycopg.connect", return_value=connection_context):
                with self.assertRaises(ValueError):
                    resolve_image_candidate_preview(
                        uuid.uuid4(), intake_root, DatabaseConfig(), "secret", company_id=uuid.uuid4(),
                    )


if __name__ == "__main__":
    unittest.main()
