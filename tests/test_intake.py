from __future__ import annotations

import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Any

from perfect_catalog.intake import (
    INTAKE_ALGORITHM,
    SecureIntakeService,
    _safe_filename,
    validate_intake,
)


def zip_bytes(files: dict[str, bytes]) -> bytes:
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return target.getvalue()


class MemoryIntakePersistence:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []
        self.hashes: set[str] = set()
        self.fail = False

    def record_intake(self, record: dict[str, Any]) -> dict[str, Any]:
        if self.fail:
            raise RuntimeError("synthetic persistence failure")
        duplicate = record["sha256"] in self.hashes
        if record["validation_status"] == "quarantined":
            self.hashes.add(record["sha256"])
        else:
            duplicate = False
        stored = {
            **record,
            "intake_submission_id": str(record["intake_submission_id"]),
            "intake_asset_id": "asset-test" if record["validation_status"] == "quarantined" else None,
            "duplicate_content": duplicate,
        }
        self.records.append(stored)
        return stored

    def intake_submissions(
        self,
        *,
        kind: str = "all",
        status: str = "all",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        items = list(reversed(self.records))
        if kind != "all":
            items = [item for item in items if item["intake_kind"] == kind]
        if status != "all":
            items = [item for item in items if item["validation_status"] == status]
        return {
            "items": items[offset : offset + limit],
            "filtered_count": len(items),
            "kind": kind,
            "status": status,
            "limit": limit,
            "offset": offset,
        }


class IntakeValidationTests(unittest.TestCase):
    def test_filename_rejects_paths_and_windows_reserved_names(self) -> None:
        self.assertEqual(_safe_filename(" Exportación.XLSX "), ("Exportación.XLSX", ".xlsx"))
        for value in ("../data.xlsx", "folder\\data.xlsx", "CON.pdf", "name.", "no-extension"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _safe_filename(value)

    def test_odoo_text_and_xlsx_require_expected_structure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory, "sample.csv")
            csv_path.write_bytes("Nombre,Referencia interna\nEmpaque,ABC-1\n".encode())
            csv_result = validate_intake(csv_path, "odoo_data", ".csv")
            self.assertTrue(csv_result.accepted)
            self.assertEqual(csv_result.report["algorithm"], INTAKE_ALGORITHM)

            xlsx_path = Path(directory, "sample.xlsx")
            xlsx_path.write_bytes(
                zip_bytes(
                    {
                        "[Content_Types].xml": b"<Types />",
                        "xl/workbook.xml": b"<workbook />",
                    }
                )
            )
            self.assertTrue(validate_intake(xlsx_path, "odoo_data", ".xlsx").accepted)
            xlsx_path.write_bytes(zip_bytes({"readme.txt": b"not a workbook"}))
            self.assertFalse(validate_intake(xlsx_path, "odoo_data", ".xlsx").accepted)

    def test_archives_reject_traversal_encryption_and_wrong_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory, "images.zip")
            archive_path.write_bytes(zip_bytes({"catalog/ABC-1.jpg": b"image-placeholder"}))
            valid = validate_intake(archive_path, "image_archive", ".zip")
            self.assertTrue(valid.accepted)
            self.assertEqual(valid.report["image_files"], 1)

            archive_path.write_bytes(zip_bytes({"../escape.jpg": b"bad"}))
            rejected = validate_intake(archive_path, "image_archive", ".zip")
            self.assertFalse(rejected.accepted)
            self.assertIn("ruta", rejected.report["errors"][0].lower())

            archive_path.write_bytes(zip_bytes({"catalog/readme.exe": b"bad"}))
            self.assertFalse(validate_intake(archive_path, "image_archive", ".zip").accepted)

    def test_indesign_package_requires_document_and_blocks_executables(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory, "indesign.zip")
            archive_path.write_bytes(zip_bytes({"catalog.idml": b"idml", "Links/photo.jpg": b"photo"}))
            self.assertTrue(validate_intake(archive_path, "indesign_package", ".zip").accepted)
            archive_path.write_bytes(zip_bytes({"catalog.idml": b"idml", "run.cmd": b"bad"}))
            self.assertFalse(validate_intake(archive_path, "indesign_package", ".zip").accepted)


class SecureIntakeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.persistence = MemoryIntakePersistence()
        self.service = SecureIntakeService(self.root, self.persistence)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def submit_pdf(self, content: bytes = b"%PDF-1.7\nsynthetic") -> dict[str, Any]:
        return self.service.submit(
            io.BytesIO(content),
            filename="Manual v2.2.pdf",
            claimed_media_type="application/pdf",
            kind="manual_pdf",
            actor="qa-user",
            reason="Documento recibido para validación",
        )

    def test_valid_original_is_content_addressed_and_duplicate_is_not_copied(self) -> None:
        first = self.submit_pdf()
        self.assertEqual(first["validation_status"], "quarantined")
        object_path = self.root.joinpath(*Path(first["storage_relpath"]).parts)
        self.assertEqual(object_path.read_bytes(), b"%PDF-1.7\nsynthetic")
        second = self.submit_pdf()
        self.assertTrue(second["duplicate_content"])
        self.assertEqual(len(list((self.root / "quarantine" / "objects").rglob("*.*"))), 0)
        self.assertEqual(len([path for path in (self.root / "quarantine" / "objects").rglob("*") if path.is_file()]), 1)

    def test_rejected_original_records_evidence_but_discards_bytes(self) -> None:
        rejected = self.submit_pdf(b"not a pdf")
        self.assertEqual(rejected["validation_status"], "rejected")
        self.assertIsNone(rejected["intake_asset_id"])
        self.assertFalse((self.root / "quarantine").exists())
        self.assertEqual(list((self.root / ".tmp").iterdir()), [])

    def test_persistence_failure_removes_new_object(self) -> None:
        self.persistence.fail = True
        with self.assertRaisesRegex(RuntimeError, "persistence"):
            self.submit_pdf()
        object_root = self.root / "quarantine" / "objects"
        self.assertEqual(
            [path for path in object_root.rglob("*") if path.is_file()] if object_root.exists() else [],
            [],
        )

    def test_kind_extension_reason_and_empty_file_are_enforced(self) -> None:
        with self.assertRaises(ValueError):
            self.service.list(kind="executable")
        with self.assertRaises(ValueError):
            self.service.list(status="deleted")
        cases = (
            {"filename": "manual.exe", "kind": "manual_pdf", "reason": "valid reason", "content": b"x"},
            {"filename": "manual.pdf", "kind": "unknown", "reason": "valid reason", "content": b"x"},
            {"filename": "manual.pdf", "kind": "manual_pdf", "reason": "no", "content": b"x"},
            {"filename": "manual.pdf", "kind": "manual_pdf", "reason": "valid reason", "content": b""},
        )
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.service.submit(
                    io.BytesIO(case["content"]),
                    filename=case["filename"],
                    claimed_media_type=None,
                    kind=case["kind"],
                    actor="qa-user",
                    reason=case["reason"],
                )


if __name__ == "__main__":
    unittest.main()
