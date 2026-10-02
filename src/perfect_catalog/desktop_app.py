"""Nexo ISA como app de escritorio: un solo acceso, una sola contraseña y una ventana propia.

Arranca la consola del operador y el generador público en este mismo proceso (localhost), pide la
contraseña de PostgreSQL UNA vez en una ventana (nunca se guarda ni va en argumentos), entra solo
a la consola con un boleto de un solo uso y abre la ventana sin pestañas ni barra de direcciones
(modo app de Edge o Chrome). Al cerrar la ventana se apagan los servidores.

Uso: INICIAR-APP.cmd (o `pythonw -m perfect_catalog.desktop_app`).
"""
from __future__ import annotations

import getpass
import logging
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

import psycopg
import uvicorn

from .config import DatabaseConfig

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOGGER = logging.getLogger("perfect_catalog.desktop_app")
OPERATOR_PORT = 8081
PUBLIC_PORT = 8082
WINDOW_FAST_EXIT_SECONDS = 8.0
MAX_PASSWORD_ATTEMPTS = 3


def find_free_port(start: int, *, attempts: int = 30, host: str = "127.0.0.1") -> int:
    """Primer puerto libre desde `start` (otro programa puede estar usando el 8081 u 8082)."""
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind((host, port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"No encontré un puerto libre cerca de {start}.")


def find_app_browser(environ: dict[str, str] | None = None) -> Path | None:
    """Edge (viene con Windows 11) o Chrome, para abrir la ventana en modo app."""
    env = environ if environ is not None else os.environ
    roots = [env.get("ProgramFiles(x86)"), env.get("ProgramFiles"), env.get("LOCALAPPDATA")]
    relatives = (
        Path("Microsoft/Edge/Application/msedge.exe"),
        Path("Google/Chrome/Application/chrome.exe"),
    )
    for relative in relatives:
        for root in roots:
            if root and (candidate := Path(root) / relative).is_file():
                return candidate
    return None


def build_app_command(browser: Path, url: str, profile_dir: Path) -> list[str]:
    return [
        str(browser), f"--app={url}", f"--user-data-dir={profile_dir}",
        "--no-first-run", "--no-default-browser-check", "--window-size=1366,880",
    ]


class ServerThread(threading.Thread):
    """Un servidor uvicorn en un hilo, que se puede apagar desde fuera."""

    def __init__(self, app: Any, port: int) -> None:
        super().__init__(daemon=True, name=f"uvicorn-{port}")
        self.port = port
        self.server = uvicorn.Server(
            # log_config=None: sin consola (pythonw) uvicorn no puede armar su formato de log
            # ("Unable to configure formatter 'default'"); los avisos van al logging normal.
            uvicorn.Config(
                app, host="127.0.0.1", port=port, log_level="warning", access_log=False,
                log_config=None,
            )
        )

    def run(self) -> None:
        try:
            self.server.run()
        except Exception:  # noqa: BLE001 - se registra; el hilo no debe tumbar la app
            LOGGER.exception("El servidor del puerto %s terminó con error", self.port)

    def wait_started(self, timeout: float = 20.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.server.started:
                return True
            if not self.is_alive():
                return False
            time.sleep(0.1)
        return False

    def stop(self) -> None:
        self.server.should_exit = True


def _ensure_std_streams() -> None:
    """pythonw no tiene consola: sys.stdout/stderr son None y cualquier librería que escriba o
    pregunte isatty() falla. Se reemplazan por un destino nulo."""
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))  # noqa: SIM115


def _setup_logging() -> None:
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        filename=str(log_dir / "desktop-app.log"), level=logging.INFO, encoding="utf-8",
        format="%(asctime)s %(levelname)s %(message)s",
    )


def ask_password(message: str) -> str | None:
    """Ventana propia para la contraseña de PostgreSQL (entrada oculta). None si se cancela."""
    import tkinter as tk

    result: dict[str, str | None] = {"value": None}
    root = tk.Tk()
    root.title("Nexo ISA")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    frame = tk.Frame(root, padx=22, pady=18)
    frame.pack()
    tk.Label(frame, text="Nexo ISA · Control de catálogo", font=("Segoe UI", 12, "bold")).pack(anchor="w")
    tk.Label(frame, text=message, justify="left", wraplength=340).pack(anchor="w", pady=(6, 10))
    entry = tk.Entry(frame, show="•", width=38)
    entry.pack(fill="x")
    entry.focus_set()

    def accept(_event: object = None) -> None:
        result["value"] = entry.get()
        root.destroy()

    buttons = tk.Frame(frame)
    buttons.pack(anchor="e", pady=(14, 0))
    tk.Button(buttons, text="Cancelar", width=10, command=root.destroy).pack(side="right", padx=(8, 0))
    tk.Button(buttons, text="Entrar", width=10, command=accept).pack(side="right")
    root.bind("<Return>", accept)
    root.bind("<Escape>", lambda _event: root.destroy())
    root.mainloop()
    return result["value"] or None


def show_error(title: str, message: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showerror(title, message, parent=root)
        root.destroy()
    except Exception:  # noqa: BLE001
        print(f"{title}: {message}", file=sys.stderr)


def connect_gateways(config: DatabaseConfig) -> tuple[Any, Any] | None:
    """Pide la contraseña (hasta 3 intentos) y devuelve los gateways ya verificados."""
    from .public_generator_api import DatabasePublicCatalogGateway
    from .reviews import DatabaseReviewGateway

    prompt = "Contraseña de PostgreSQL (no se guarda en ningún archivo)."
    for attempt in range(1, MAX_PASSWORD_ATTEMPTS + 1):
        password = ask_password(prompt)
        if password is None:
            return None
        review_gateway = DatabaseReviewGateway(config, password)
        try:
            review_gateway.plans(limit=1)
        except psycopg.Error as exc:
            review_gateway.close()
            LOGGER.warning("Conexión rechazada (intento %s): %s", attempt, type(exc).__name__)
            prompt = "No pude conectar con esa contraseña (o PostgreSQL está apagado). Inténtalo de nuevo."
            continue
        public_gateway = DatabasePublicCatalogGateway(config, password)
        return review_gateway, public_gateway
    show_error("Nexo ISA", "No se pudo conectar a PostgreSQL. Revisa que el servicio esté encendido y la contraseña.")
    return None


def _control_window(url: str) -> None:
    """Respaldo cuando no hay Edge/Chrome en modo app: una ventanita para mantener el servidor vivo."""
    import tkinter as tk

    root = tk.Tk()
    root.title("Nexo ISA")
    frame = tk.Frame(root, padx=22, pady=18)
    frame.pack()
    tk.Label(frame, text="Nexo ISA está en marcha", font=("Segoe UI", 12, "bold")).pack(anchor="w")
    tk.Label(frame, text="Cierra esta ventana para apagar la consola.", justify="left").pack(anchor="w", pady=(6, 10))
    tk.Button(frame, text="Abrir de nuevo", command=lambda: webbrowser.open(url)).pack(side="left")
    tk.Button(frame, text="Apagar", command=root.destroy).pack(side="right")
    root.mainloop()


def main() -> int:
    _ensure_std_streams()
    os.chdir(PROJECT_ROOT)
    _setup_logging()
    try:
        from .operator_api import OperatorAuthenticator, create_operator_app
        from .public_generator_api import create_public_generator_app

        config = DatabaseConfig.from_args(object())
        gateways = connect_gateways(config)
        if gateways is None:
            return 2
        review_gateway, public_gateway = gateways

        actor = getpass.getuser()
        # El código temporal existe pero nadie lo ve: la app entra con un boleto de un solo uso.
        authenticator = OperatorAuthenticator(actor, secrets.token_urlsafe(24))
        operator_port = find_free_port(OPERATOR_PORT)
        public_port = find_free_port(max(PUBLIC_PORT, operator_port + 1))

        operator = ServerThread(
            create_operator_app(
                review_gateway, authenticator,
                intake_root=Path("data/intake"), promotion_output_dir=Path("data/exports/imports"),
                catalog_output_dir=Path("data/exports/catalogs"), image_output_dir=Path("data/images"),
                public_generator_base_url=f"http://127.0.0.1:{public_port}",
            ),
            operator_port,
        )
        public = ServerThread(create_public_generator_app(public_gateway), public_port)
        operator.start()
        public.start()
        if not (operator.wait_started() and public.wait_started()):
            show_error("Nexo ISA", "No se pudieron iniciar los servidores locales. Mira logs\\desktop-app.log.")
            return 3
        LOGGER.info("Consola en %s; generador público en %s", operator_port, public_port)

        url = f"http://127.0.0.1:{operator_port}/operator/app-login?ticket={authenticator.issue_launch_ticket()}"
        browser = find_app_browser()
        try:
            if browser is not None:
                profile = Path(os.environ.get("LOCALAPPDATA", str(PROJECT_ROOT))) / "NexoISA" / "perfil"
                profile.mkdir(parents=True, exist_ok=True)
                started = time.monotonic()
                process = subprocess.Popen(build_app_command(browser, url, profile))
                process.wait()
                if time.monotonic() - started < WINDOW_FAST_EXIT_SECONDS:
                    # El navegador cedió el control a otra instancia: se mantiene el servidor con la ventanita.
                    fresh = f"http://127.0.0.1:{operator_port}/operator/app-login?ticket={authenticator.issue_launch_ticket()}"
                    webbrowser.open(fresh)
                    _control_window(fresh)
            else:
                webbrowser.open(url)
                _control_window(url)
        finally:
            operator.stop()
            public.stop()
            review_gateway.close()
            public_gateway.close()
            operator.join(timeout=5)
            public.join(timeout=5)
        return 0
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("La app terminó con error")
        show_error("Nexo ISA", f"La app no pudo arrancar: {exc}\n\nDetalle en logs\\desktop-app.log.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
