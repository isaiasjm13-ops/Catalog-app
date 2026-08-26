import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from perfect_catalog.approved_image_materialization import _copy_verified_member


class ApprovedImageMaterializationTests(unittest.TestCase):
    def test_member_is_copied_content_addressed_without_changing_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "images.zip"
            content = b"synthetic-image-bytes"
            with zipfile.ZipFile(archive, "w") as target:
                target.writestr("images/NK-001.jpg", content)
            before = archive.read_bytes()
            with zipfile.ZipFile(archive) as source:
                info = source.getinfo("images/NK-001.jpg")
            digest = hashlib.sha256(content).hexdigest()
            destination = root / "objects" / digest[:2] / f"{digest}.jpg"
            _copy_verified_member(archive, info.filename, digest, len(content), f"{info.CRC:08x}", destination)
            self.assertEqual(destination.read_bytes(), content)
            self.assertEqual(archive.read_bytes(), before)
            _copy_verified_member(archive, info.filename, digest, len(content), f"{info.CRC:08x}", destination)

    def test_wrong_hash_never_publishes_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "images.zip"
            with zipfile.ZipFile(archive, "w") as target:
                target.writestr("NK-001.jpg", b"actual")
            with zipfile.ZipFile(archive) as source:
                info = source.getinfo("NK-001.jpg")
            destination = root / "objects" / "bad.jpg"
            with self.assertRaisesRegex(RuntimeError, "SHA-256"):
                _copy_verified_member(archive, info.filename, "0" * 64, info.file_size, f"{info.CRC:08x}", destination)
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
