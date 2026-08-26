from __future__ import annotations

import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from perfect_catalog.image_archive_index import IMAGE_INDEX_ALGORITHM, inspect_image_archive, normalize_image_key


class ImageArchiveIndexTests(unittest.TestCase):
    def test_normalization_is_stable_but_does_not_claim_a_product_match(self) -> None:
        self.assertEqual(normalize_image_key("ÁBC 001-final.JPG"), "ABC-001-FINAL")

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
