from __future__ import annotations

import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

from perfect_catalog.cli import build_parser
from perfect_catalog import intake_promotion
from perfect_catalog.intake_promotion import PROMOTION_ALGORITHM, _confined, _profile_suggestions


class IntakePromotionUnitTests(unittest.TestCase):
    def test_promotion_holds_a_session_lock_while_the_locked_work_runs(self) -> None:
        submission_id = uuid.uuid4()
        config = mock.MagicMock()
        config.connection_kwargs.return_value = {"host": "localhost"}
        connection = mock.MagicMock()
        connection_context = mock.MagicMock()
        connection_context.__enter__.return_value = connection
        with (
            mock.patch.object(intake_promotion.psycopg, "connect", return_value=connection_context) as connect,
            mock.patch.object(
                intake_promotion, "_promote_intake_to_dry_run_locked",
                return_value={"status": "promoted"},
            ) as locked,
        ):
            result = intake_promotion.promote_intake_to_dry_run(
                submission_id, Path("intake"), config, "secret", Path("reports"),
                actor="qa", reason="Prueba de bloqueo", brand_code="A1",
            )
        self.assertEqual(result["status"], "promoted")
        self.assertTrue(connect.call_args.kwargs["autocommit"])
        self.assertEqual(connection.execute.call_count, 2)
        self.assertIn("pg_advisory_lock", connection.execute.call_args_list[0].args[0])
        self.assertIn("pg_advisory_unlock", connection.execute.call_args_list[1].args[0])
        locked.assert_called_once()

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
