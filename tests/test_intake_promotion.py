from __future__ import annotations

import tempfile
import unittest
import uuid
from pathlib import Path

from perfect_catalog.cli import build_parser
from perfect_catalog.intake_promotion import PROMOTION_ALGORITHM, _confined, _profile_suggestions


class IntakePromotionUnitTests(unittest.TestCase):
    def test_processing_paths_are_confined(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            expected = root / "processing" / str(uuid.uuid4()) / "sample.csv"
            self.assertEqual(_confined(root, expected.relative_to(root).as_posix()), expected)
            for value in ("../escape.csv", "processing/../escape.csv", "/absolute.csv"):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    _confined(root, value)

    def test_profile_aliases_are_suggestions_with_versioned_provenance(self) -> None:
        profile = {"workbook": {"sheets": [{"name": "Productos", "headers": ["SKU", "Descripción"]}]}}
        result = _profile_suggestions(profile)
        self.assertEqual(result["algorithm"], PROMOTION_ALGORITHM)
        self.assertEqual(result["sheets"][0]["columns"]["internal_reference"], "SKU")

    def test_cli_requires_human_evidence(self) -> None:
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["promote-intake", str(uuid.uuid4())])
        args = parser.parse_args([
            "promote-intake", str(uuid.uuid4()), "--actor", "qa-user",
            "--reason", "Perfilado solicitado por control de calidad",
        ])
        self.assertEqual(args.command, "promote-intake")

