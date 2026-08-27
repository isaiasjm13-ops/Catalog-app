from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


class PackagingTests(unittest.TestCase):
    def test_installed_console_api_imports_outside_repository_root(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "from perfect_catalog.api import API_VERSION; "
                "from perfect_catalog.operator_api import OPERATOR_VERSION, _templates; "
                "from perfect_catalog.publication import build_release; "
                "from tools.odoo_profiler import read_tabular_source; "
                "assert _templates().get_template('operator_login.html'); "
                "print(API_VERSION, OPERATOR_VERSION)",
            ],
            cwd=Path(__file__).resolve().parent,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), "1.2.0 1.30.0")


if __name__ == "__main__":
    unittest.main()
