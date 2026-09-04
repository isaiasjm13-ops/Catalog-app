from __future__ import annotations

import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from perfect_catalog.image_archive_index import (
    IMAGE_INDEX_ALGORITHM, inspect_image_archive, normalize_image_key, split_variant_suffix,
)


class ImageArchiveIndexTests(unittest.TestCase):
    def test_normalization_is_stable_but_does_not_claim_a_product_match(self) -> None:
        self.assertEqual(normalize_image_key("ÁBC 001-final.JPG"), "ABC-001-FINAL")

    def test_variant_suffix_is_split_from_the_base_reference(self) -> None:
        self.assertEqual(split_variant_suffix("REF-1234-2"), ("REF-1234", 2))
        self.assertEqual(split_variant_suffix("REF-1234-10"), ("REF-1234", 10))
        self.assertEqual(split_variant_suffix("REF-1234"), ("REF-1234", None))
        self.assertEqual(split_variant_suffix("REF-1234-1"), ("REF-1234-1", None))
        self.assertEqual(split_variant_suffix("REF-1234-0"), ("REF-1234-0", None))

    def test_letter_variant_suffix_matches_the_real_naming_convention(self) -> None:
        """Convención real reportada por el usuario: `CKT-507AU-LB A`, `CKT-507AU-LB - A` y
        `CKT-507AU-LB (A)` normalizan igual (espacios/guiones/paréntesis se colapsan a `-`), y
        la letra A significa "foto principal" (igual que no tener sufijo); B, C, D... son
        fotos adicionales."""
        self.assertEqual(normalize_image_key("CKT-507AU-LB A.jpg"), "CKT-507AU-LB-A")
        self.assertEqual(normalize_image_key("CKT-507AU-LB - A.jpg"), "CKT-507AU-LB-A")
        self.assertEqual(normalize_image_key("CKT-507AU-LB (A).jpg"), "CKT-507AU-LB-A")
        self.assertEqual(split_variant_suffix("CKT-507AU-LB-A"), ("CKT-507AU-LB", None))
        self.assertEqual(split_variant_suffix("CKT-507AU-LB-B"), ("CKT-507AU-LB", 2))
        self.assertEqual(split_variant_suffix("CKT-507AU-LB-C"), ("CKT-507AU-LB", 3))
        self.assertEqual(split_variant_suffix("CKT-507AU-LB-F"), ("CKT-507AU-LB", 6))
        self.assertEqual(split_variant_suffix("CKT-507AU-LB-Z"), ("CKT-507AU-LB", 26))

    def test_index_hashes_streams_and_marks_collisions_without_extracting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path = root / "images.zip"
            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("front/ABC-001.jpg", b"first-image")
                archive.writestr("back/ABC 001.png", b"second-image")
                archive.writestr("unique/XYZ-9.webp", b"third-image")
            before = {path.relative_to(root) for path in root.rglob("*")}
            report = inspect_image_archive(archive_path)
            after = {path.relative_to(root) for path in root.rglob("*")}
        self.assertEqual(before, after)
        self.assertEqual(report["algorithm"], IMAGE_INDEX_ALGORITHM)
        self.assertEqual(report["image_count"], 3)
        self.assertEqual(report["ambiguous_entries"], 2)
        self.assertEqual([entry["match_status"] for entry in report["entries"]], ["ambiguous", "ambiguous", "unmatched"])
        self.assertEqual(report["entries"][0]["content_sha256"], hashlib.sha256(b"first-image").hexdigest())
        self.assertTrue(all("product" not in entry for entry in report["entries"]))
        self.assertTrue(all("storage" not in entry for entry in report["entries"]))

    def test_archive_without_images_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "sidecars.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("refs.csv", "ref,name")
            with self.assertRaisesRegex(ValueError, "imágenes"):
                inspect_image_archive(archive_path)
