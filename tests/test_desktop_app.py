from __future__ import annotations

import socket
import tempfile
import unittest
from pathlib import Path

from perfect_catalog.desktop_app import (
    build_app_command,
    find_app_browser,
    find_free_port,
)

ROOT = Path(__file__).resolve().parents[1]


class FindFreePortTests(unittest.TestCase):
    def test_skips_a_port_that_another_program_is_using(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as busy:
            busy.bind(("127.0.0.1", 0))
            busy.listen(1)
            taken = busy.getsockname()[1]
            chosen = find_free_port(taken)
        self.assertGreater(chosen, taken)

    def test_returns_the_first_port_when_it_is_free(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            free = probe.getsockname()[1]
        self.assertEqual(find_free_port(free), free)


class FindAppBrowserTests(unittest.TestCase):
    def test_prefers_edge_and_falls_back_to_chrome(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            chrome = root / "Google/Chrome/Application/chrome.exe"
            chrome.parent.mkdir(parents=True)
            chrome.write_bytes(b"")
            env = {"ProgramFiles": str(root)}
            self.assertEqual(find_app_browser(env), chrome)
            edge = root / "Microsoft/Edge/Application/msedge.exe"
            edge.parent.mkdir(parents=True)
            edge.write_bytes(b"")
            self.assertEqual(find_app_browser(env), edge)

    def test_returns_none_when_no_browser_is_installed(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(find_app_browser({"ProgramFiles": folder}))
        self.assertIsNone(find_app_browser({}))


class BuildAppCommandTests(unittest.TestCase):
    def test_opens_a_chromeless_window_with_its_own_profile(self) -> None:
        command = build_app_command(Path("C:/edge/msedge.exe"), "http://127.0.0.1:8081/operator/app-login?ticket=abc", Path("C:/perfil"))
        self.assertTrue(command[0].endswith("msedge.exe"))
        self.assertIn("--app=http://127.0.0.1:8081/operator/app-login?ticket=abc", command)
        self.assertTrue(any(part.startswith("--user-data-dir=") for part in command))
        # El perfil propio evita que Edge ceda la ventana a una instancia ya abierta
        # (y que la app crea que se cerró al instante).
        self.assertIn("--no-first-run", command)


class NoConsoleTests(unittest.TestCase):
    def test_streams_are_replaced_when_there_is_no_console_like_pythonw(self) -> None:
        import sys
        from unittest import mock

        from perfect_catalog.desktop_app import _ensure_std_streams

        with mock.patch.object(sys, "stdout", None), mock.patch.object(sys, "stderr", None):
            _ensure_std_streams()
            self.assertIsNotNone(sys.stdout)
            self.assertIsNotNone(sys.stderr)
            sys.stderr.write("texto que antes habría fallado")  # escribir no debe lanzar
            sys.stdout.flush()

    def test_uvicorn_does_not_configure_its_own_logging_formatter(self) -> None:
        # Sin consola, uvicorn fallaba con "Unable to configure formatter 'default'".
        from perfect_catalog.desktop_app import ServerThread

        thread = ServerThread(lambda scope, receive, send: None, 0)
        self.assertIsNone(thread.server.config.log_config)


class DesktopAppWiringTests(unittest.TestCase):
    def test_launcher_and_guards_know_about_the_desktop_app(self) -> None:
        launcher = (ROOT / "INICIAR-APP.cmd").read_text(encoding="utf-8")
        self.assertIn("pythonw.exe", launcher)
        self.assertIn("perfect_catalog.desktop_app", launcher)
        for script in ("db/bootstrap/run_pending_migrations.ps1", "db/bootstrap/clear_imported_data.ps1"):
            text = (ROOT / script).read_text(encoding="utf-8")
            self.assertIn("perfect_catalog.desktop_app", text, script)

    def test_password_is_never_read_from_arguments_files_or_environment(self) -> None:
        source = (ROOT / "src/perfect_catalog/desktop_app.py").read_text(encoding="utf-8")
        self.assertIn("ask_password", source)
        for forbidden in ("PGPASSWORD", "sys.argv", "read_text(", "getpass.getpass"):
            self.assertNotIn(forbidden, source)

    def test_shortcut_script_targets_the_venv_pythonw_and_the_brand_icon(self) -> None:
        script = (ROOT / "scripts/crear-acceso-directo.ps1").read_text(encoding="utf-8")
        self.assertIn("pythonw.exe", script)
        self.assertIn("-m perfect_catalog.desktop_app", script)
        self.assertIn("nexo-isa.ico", script)
        self.assertTrue((ROOT / "src/perfect_catalog/static/nexo-isa.ico").is_file())


if __name__ == "__main__":
    unittest.main()
