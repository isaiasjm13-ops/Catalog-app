"""App FastAPI standalone y separada del operador: generador público de catálogos.

Sin sesión, sin código de acceso — el único control de entrada es poseer un link
(`token`) que un operador ya autenticado creó desde `/operator/public-links`. No
reutiliza `_same_origin` de `operator_api.py` (hardcodeado a localhost): el anti-CSRF
aquí es un ticket firmado (HMAC) que viaja en cookie + campo oculto, y no depende del
host, así que esta app puede exponerse en un dominio público real más adelante.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import logging
import secrets
import sys
import threading
import time
import uuid
from datetime import UTC, datetime
from importlib.resources import files
from typing import Any, Callable, Protocol

import psycopg
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import DatabaseConfig, prompt_password
from .public_catalog import (
    MAX_PUBLIC_EXCEL_BYTES,
    MAX_PUBLIC_IMAGE_FILES,
    MAX_PUBLIC_IMAGE_TOTAL_BYTES,
    generate_public_catalog,
)

PUBLIC_GENERATOR_VERSION = "1.0.0"
LOGGER = logging.getLogger(__name__)
TICKET_COOKIE = "pc_public_ticket"
TICKET_TTL_SECONDS = 30 * 60
MAX_DECLARED_NAME_LENGTH = 200
MAX_COMPANY_NAME_LENGTH = 200
MAX_BRAND_NAME_LENGTH = 120
MAX_REQUEST_BYTES = MAX_PUBLIC_EXCEL_BYTES + MAX_PUBLIC_IMAGE_TOTAL_BYTES + 8 * 1024 * 1024
MAX_FORM_PART_BYTES = 20 * 1024 * 1024


class PublicCatalogGateway(Protocol):
    def resolve_link(self, token: str) -> dict[str, Any] | None: ...

    def record_generation(
        self, *, link_id: uuid.UUID, declared_name: str, product_count: int,
        matched_image_count: int, unmatched_image_count: int, ambiguous_image_count: int,
        excel_sha256: str, client_ip: str | None,
    ) -> dict[str, Any]: ...


class DatabasePublicCatalogGateway:
    def __init__(self, config: DatabaseConfig, password: str) -> None:
        self._config = config
        self._password = password

    def close(self) -> None:
        self._password = ""

    def resolve_link(self, token: str) -> dict[str, Any] | None:
        from .public_catalog_links import resolve_public_catalog_link
        return resolve_public_catalog_link(self._config, self._password, token=token)

    def record_generation(self, **kwargs: Any) -> dict[str, Any]:
        from .public_catalog_links import record_public_catalog_generation
        return record_public_catalog_generation(self._config, self._password, **kwargs)


class _TicketSigner:
    """Anti-CSRF autocontenido: firma HMAC con expiración embebida, sin sesión de
    servidor. Mismo idioma que `OperatorAuthenticator._sign/_unsign`, pero stateless
    (no depende de un diccionario de sesiones ni del host de la petición)."""

    def __init__(self) -> None:
        self._key = secrets.token_bytes(32)

    def issue(self, ref: str) -> str:
        expires_at = int(time.time()) + TICKET_TTL_SECONDS
        payload = f"{expires_at}:{ref}"
        encoded = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")
        signature = hmac.new(self._key, encoded.encode("ascii"), hashlib.sha256).hexdigest()
        return f"{encoded}.{signature}"

    def verify(self, ticket: str | None) -> str | None:
        """Devuelve el `ref` embebido si la firma y la expiración son válidas, si no None."""
        try:
            encoded, signature = str(ticket or "").split(".", 1)
            expected = hmac.new(self._key, encoded.encode("ascii"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                return None
            expires_text, ref = base64.urlsafe_b64decode(encoded.encode("ascii")).decode("utf-8").split(":", 1)
            if int(expires_text) < int(time.time()):
                return None
            return ref
        except (ValueError, UnicodeDecodeError, TypeError):
            return None


class _SlidingWindowLimiter:
    """Ventana deslizante en memoria; mismo patrón que el contador de intentos de
    login fallidos de `OperatorAuthenticator`, generalizado a una clave arbitraria
    (token de link o IP) en vez de una única lista global."""

    def __init__(self, *, max_events: int, window_seconds: float, now: Callable[[], float] = time.time) -> None:
        self._max_events = max_events
        self._window = window_seconds
        self._now = now
        self._events: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self._now()
        with self._lock:
            events = [moment for moment in self._events.get(key, []) if now - moment < self._window]
            if len(events) >= self._max_events:
                self._events[key] = events
                return False
            events.append(now)
            self._events[key] = events
            return True


def _templates() -> Environment:
    template_dir = files("perfect_catalog").joinpath("templates")
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(("html", "xml")),
        undefined=StrictUndefined,
    )


def _render(environment: Environment, name: str, **context: Any) -> HTMLResponse:
    context.setdefault("version", PUBLIC_GENERATOR_VERSION)
    return HTMLResponse(environment.get_template(name).render(**context))


def _set_security_headers(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _error(environment: Environment, status_code: int, title: str, detail: str) -> HTMLResponse:
    response = _render(environment, "public_generator_error.html", title=title, detail=detail)
    response.status_code = status_code
    return response


def _safe_download_name(company_name: str) -> str:
    slug = "".join(char if char.isalnum() else "-" for char in company_name.strip().lower())
    slug = "-".join(part for part in slug.split("-") if part) or "catalogo"
    return f"catalogo-{slug}-{datetime.now(UTC):%Y%m%d}.html"


def create_public_generator_app(
    gateway: PublicCatalogGateway,
    *,
    link_rate_limit: int = 20,
    link_rate_window_seconds: float = 3600.0,
    ip_rate_limit: int = 10,
    ip_rate_window_seconds: float = 3600.0,
) -> FastAPI:
    environment = _templates()
    signer = _TicketSigner()
    link_limiter = _SlidingWindowLimiter(max_events=link_rate_limit, window_seconds=link_rate_window_seconds)
    ip_limiter = _SlidingWindowLimiter(max_events=ip_rate_limit, window_seconds=ip_rate_window_seconds)

    app = FastAPI(title="Generador público de catálogos", version=PUBLIC_GENERATOR_VERSION, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def _security_headers_middleware(request: Request, call_next: Any) -> Response:
        response = await call_next(request)
        _set_security_headers(response)
        return response

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(_: Request, exc: StarletteHTTPException) -> HTMLResponse:
        return _error(environment, int(exc.status_code), "No disponible", str(exc.detail))

    @app.get("/generar", response_class=HTMLResponse)
    async def generator_form(request: Request, ref: str = "") -> Response:
        link = await run_in_threadpool(gateway.resolve_link, ref) if ref else None
        if link is None:
            return _error(
                environment, 404, "Link no encontrado",
                "Este link no existe, fue revocado, o falta el parámetro ref en la URL. "
                "Pide un link nuevo a quien te dio acceso.",
            )
        ticket = signer.issue(ref)
        response = _render(environment, "public_generator_form.html", ref=ref, csrf_token=ticket, link_label=link["label"])
        response.set_cookie(
            TICKET_COOKIE, ticket, max_age=TICKET_TTL_SECONDS, httponly=True, samesite="strict",
        )
        return response

    @app.post("/generar", response_class=HTMLResponse)
    async def generator_submit(request: Request) -> Response:
        content_type = request.headers.get("content-type", "")
        if not content_type.lower().startswith("multipart/form-data;"):
            return _error(environment, 415, "Formulario inválido", "La carga debe usar multipart/form-data.")
        try:
            content_length = int(request.headers.get("content-length", ""))
        except ValueError:
            return _error(environment, 411, "Longitud requerida", "La carga debe declarar un tamaño válido.")
        if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
            return _error(environment, 413, "Carga demasiado grande", "La solicitud supera el límite del generador (excel + fotos).")

        try:
            async with request.form(
                max_files=MAX_PUBLIC_IMAGE_FILES + 3, max_fields=16, max_part_size=MAX_FORM_PART_BYTES,
            ) as form:
                csrf_cookie = request.cookies.get(TICKET_COOKIE)
                csrf_field = str(form.get("csrf_token") or "")
                if not csrf_cookie or not hmac.compare_digest(csrf_cookie, csrf_field):
                    raise PermissionError("La evidencia del formulario no coincide; recarga la página e inténtalo de nuevo.")
                ref = signer.verify(csrf_cookie)
                if ref is None:
                    raise PermissionError("El formulario expiró; recarga la página e inténtalo de nuevo.")

                client_ip = _client_ip(request)
                if not link_limiter.allow(ref):
                    raise PermissionError("Este link generó demasiados catálogos en poco tiempo. Intenta más tarde.")
                if client_ip and not ip_limiter.allow(client_ip):
                    raise PermissionError("Se generaron demasiados catálogos desde esta conexión en poco tiempo. Intenta más tarde.")

                link = await run_in_threadpool(gateway.resolve_link, ref)
                if link is None:
                    raise PermissionError("Este link ya no está activo.")

                declared_name = str(form.get("declared_name") or "").strip()
                if not declared_name or len(declared_name) > MAX_DECLARED_NAME_LENGTH:
                    raise ValueError("Escribe tu nombre o el de tu empresa (hasta 200 caracteres).")
                company_name = str(form.get("company_name") or "").strip()
                brand_name = str(form.get("brand_name") or "").strip()
                primary_color = str(form.get("primary_color") or "")
                secondary_color = str(form.get("secondary_color") or "")

                odoo_upload = form.get("odoo_file")
                if not isinstance(odoo_upload, UploadFile) or not odoo_upload.filename:
                    raise ValueError("Selecciona el Excel de productos.")
                excel_bytes = await odoo_upload.read()

                image_uploads = [item for item in form.getlist("images") if isinstance(item, UploadFile) and item.filename]
                images = [(str(item.filename), await item.read()) for item in image_uploads]

                logo_upload = form.get("logo")
                logo: tuple[str, bytes] | None = None
                if isinstance(logo_upload, UploadFile) and logo_upload.filename:
                    logo = (str(logo_upload.filename), await logo_upload.read())

                result = await run_in_threadpool(
                    generate_public_catalog,
                    excel_bytes=excel_bytes, excel_filename=str(odoo_upload.filename), images=images,
                    company_name=company_name, brand_name=brand_name,
                    primary_color=primary_color, secondary_color=secondary_color, logo=logo,
                )
                await run_in_threadpool(
                    gateway.record_generation,
                    link_id=uuid.UUID(str(link["public_catalog_link_id"])), declared_name=declared_name,
                    product_count=result.product_count, matched_image_count=result.matched_image_count,
                    unmatched_image_count=result.unmatched_image_count,
                    ambiguous_image_count=result.ambiguous_image_count,
                    excel_sha256=result.excel_sha256, client_ip=client_ip,
                )
        except (ValueError, PermissionError) as exc:
            return _error(environment, 400, "No se pudo generar el catálogo", str(exc))
        except Exception as exc:
            diagnostic_id = secrets.token_hex(4)
            LOGGER.error("public_catalog_generation_failed diagnostic_id=%s error_type=%s", diagnostic_id, type(exc).__name__)
            return _error(
                environment, 503, "Generador no disponible",
                f"No se completó la generación. Diagnóstico {diagnostic_id}.",
            )

        response = Response(content=result.html, media_type="text/html")
        response.headers["Content-Disposition"] = f'attachment; filename="{_safe_download_name(company_name)}"'
        # El ticket NO se borra: es anti-CSRF (prueba que el POST vino de una página que
        # nosotros mismos servimos), no un nonce de un solo uso. Borrarlo rompía generar
        # un segundo catálogo (ajustar colores y volver a enviar) sin recargar la página,
        # porque el campo oculto del formulario ya cargado seguía teniendo el valor viejo.
        return response

    return app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inicia el generador público de catálogos (sin login).")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8082)
    parser.add_argument("--database", default=None)
    parser.add_argument("--user", default=None)
    parser.add_argument("--db-host", dest="host_db", default=None)
    parser.add_argument("--db-port", dest="port_db", type=int, default=None)
    parser.add_argument("--prompt-password", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    gateway: DatabasePublicCatalogGateway | None = None
    try:
        database_args = argparse.Namespace(
            host=args.host_db, port=args.port_db, database=args.database, user=args.user,
        )
        config = DatabaseConfig.from_args(database_args)
        database_password = prompt_password(args.prompt_password)
        gateway = DatabasePublicCatalogGateway(config, database_password)
        gateway.resolve_link("healthcheck")
        database_password = ""
    except (ValueError, EOFError, KeyboardInterrupt, psycopg.Error) as exc:
        if gateway is not None:
            gateway.close()
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Generador público: http://{args.host}:{args.port}/generar?ref=<token-del-link>")
    print("Crea y administra los links desde /operator/public-links en la consola de operador.")
    print("Presiona Ctrl+C para detener.")
    uvicorn.run(create_public_generator_app(gateway), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
