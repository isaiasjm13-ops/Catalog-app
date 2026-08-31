from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import hmac
import logging
import re
import secrets
import sys
import threading
import time
import uuid
import webbrowser
from contextlib import asynccontextmanager
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.parse import parse_qs, urlencode, urlsplit

import uvicorn
import psycopg
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import DatabaseConfig, prompt_password
from .catalog_export_job import (
    CATALOG_THEMES,
    INDESIGN_TEMPLATE_PROFILES,
    SUPPORTED_FORMATS,
    estimate_indesign_layout,
    list_indesign_preflight_receipts,
    record_indesign_preflight,
    resolve_indesign_preflight_receipt,
    MAX_INDESIGN_PREFLIGHT_BYTES,
    list_operator_catalog_exports,
    resolve_catalog_download,
)
from .intake import (
    INTAKE_KINDS,
    MAX_UPLOAD_REQUEST_BYTES,
    SecureIntakeService,
    intake_kind_options,
)
from .importer import DEFAULT_MAX_PILOT_ROWS
from .reviews import DatabaseReviewGateway, REVIEW_STATES, _require_text


OPERATOR_VERSION = "1.39.1"
LOGGER = logging.getLogger(__name__)
SESSION_COOKIE = "pc_operator_session"
LOGIN_COOKIE = "pc_operator_login"
LOGIN_COOKIE_PATH = "/operator"
MAX_FORM_BYTES = 16_384
MAX_REASON_LENGTH = 500
SESSION_TTL_SECONDS = 60 * 60
LOGIN_CHALLENGE_TTL_SECONDS = 10 * 60
PBKDF2_ITERATIONS = 310_000


class ReviewGateway(Protocol):
    def close(self) -> None: ...

    def companies(self) -> list[dict[str, Any]]: ...

    def authorize_company_resource(
        self, company_id: uuid.UUID, resource_type: str, resource_id: uuid.UUID,
    ) -> bool: ...

    def plans(self, *, limit: int = 100, company_id: uuid.UUID | None = None) -> list[dict[str, Any]]: ...

    def plan(self, plan_id: uuid.UUID) -> dict[str, Any] | None: ...

    def import_plan(self, plan_id: uuid.UUID) -> dict[str, Any]: ...

    def approve_import_plan(
        self, plan_id: uuid.UUID, fingerprint: str, actor: str, reason: str,
    ) -> dict[str, Any]: ...

    def apply_import_plan(
        self, plan_id: uuid.UUID, fingerprint: str, actor: str, reason: str,
    ) -> dict[str, Any]: ...

    def prepare_import_plan(
        self, plan_id: uuid.UUID, fingerprint: str, actor: str, reason: str,
        brand_code: str,
    ) -> dict[str, Any]: ...

    def page(
        self,
        plan_id: uuid.UUID,
        fingerprint: str,
        *,
        query: str = "",
        state: str = "all",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]: ...

    def decide(
        self,
        plan_id: uuid.UUID,
        product_id: uuid.UUID,
        fingerprint: str,
        review_sha256: str,
        decision: str,
        actor: str,
        reason: str,
    ) -> dict[str, Any]: ...

    def decide_many(
        self, plan_id: uuid.UUID, fingerprint: str, decision: str,
        actor: str, reason: str, *, query: str, expected_count: int,
    ) -> dict[str, Any]: ...

    def intake_submissions(
        self,
        *,
        kind: str = "all",
        status: str = "all",
        limit: int = 50,
        offset: int = 0,
        company_id: uuid.UUID | None = None,
    ) -> dict[str, Any]: ...

    def record_intake(self, record: dict[str, Any]) -> dict[str, Any]: ...

    def promote_intake(
        self, submission_id: uuid.UUID, intake_root: Path, output_dir: Path,
        actor: str, reason: str, max_rows: int,
    ) -> dict[str, Any]: ...

    def index_image_archive(
        self, submission_id: uuid.UUID, intake_root: Path, actor: str, reason: str,
    ) -> dict[str, Any]: ...

    def generate_image_candidates(
        self, image_archive_index_id: uuid.UUID, actor: str, reason: str,
        company_id: uuid.UUID,
    ) -> dict[str, Any]: ...

    def image_candidates(
        self, *, limit: int = 100, offset: int = 0, company_id: uuid.UUID,
    ) -> dict[str, Any]: ...

    def decide_image_candidate(
        self, candidate_id: uuid.UUID, evidence_sha256: str, decision: str,
        actor: str, reason: str, company_id: uuid.UUID,
    ) -> dict[str, Any]: ...

    def decide_image_candidates_bulk(
        self, expected_count: int, decision: str, actor: str, reason: str,
        company_id: uuid.UUID,
    ) -> dict[str, Any]: ...

    def materialize_approved_image(
        self, candidate_id: uuid.UUID, evidence_sha256: str,
        intake_root: Path, image_root: Path, actor: str, reason: str,
        company_id: uuid.UUID,
    ) -> dict[str, Any]: ...

    def materialize_approved_images_bulk(
        self, expected_count: int, intake_root: Path, image_root: Path,
        actor: str, reason: str, company_id: uuid.UUID,
    ) -> dict[str, Any]: ...

    def catalog_releases(self, *, limit: int = 100, company_id: uuid.UUID | None = None) -> list[dict[str, Any]]: ...

    def brand_profiles(self, *, company_id: uuid.UUID) -> list[dict[str, Any]]: ...

    def create_brand_profile(
        self, values: dict[str, str], actor: str, reason: str, company_id: uuid.UUID,
    ) -> dict[str, Any]: ...

    def visual_identities(self, *, company_id: uuid.UUID) -> dict[str, Any]: ...

    def create_visual_identity(self, **kwargs: Any) -> dict[str, Any]: ...
    def visual_identity_asset(self, revision_id: uuid.UUID, asset_root: Path) -> tuple[Path, str]: ...

    def export_catalog(
        self, release_id: uuid.UUID, output_root: Path,
        *, formats: tuple[str, ...], export_config: dict[str, Any],
        image_root: Path | None = None,
        brand_asset_root: Path | None = None,
    ) -> dict[str, Any]: ...

    def build_catalog_release(
        self, plan_id: uuid.UUID, fingerprint: str, version: str,
        actor: str, reason: str, brand: str,
    ) -> dict[str, Any]: ...

    def publish_catalog_release(
        self, release_id: uuid.UUID, snapshot_sha256: str, actor: str, reason: str,
    ) -> dict[str, Any]: ...

    def preview_catalog_release(
        self, release_id: uuid.UUID, *, group_by: str, group_by_secondary: str = "",
        filter_field: str = "all", filter_query: str = "", selected_references: str = "",
        sample_limit: int = 24,
    ) -> dict[str, Any]: ...

    def catalog_preview_image(
        self, release_id: uuid.UUID, item_number: int, image_root: Path,
    ) -> Path: ...

    def catalog_release_products(
        self, release_id: uuid.UUID, *, query: str = "", limit: int = 24, offset: int = 0,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class OperatorSession:
    session_id: str
    actor: str
    csrf_token: str
    expires_at: int
    company_id: uuid.UUID | None = None
    company_code: str | None = None
    company_name: str | None = None


class OperatorAuthenticator:
    def __init__(
        self,
        actor: str,
        access_code: str,
        *,
        session_ttl_seconds: int = SESSION_TTL_SECONDS,
        now: Callable[[], float] = time.time,
        pbkdf2_iterations: int = PBKDF2_ITERATIONS,
    ) -> None:
        self.actor = _require_text(actor, "actor")
        if len(self.actor) > 120:
            raise ValueError("actor no puede superar 120 caracteres.")
        if len(access_code) < 12:
            raise ValueError("El código de acceso temporal debe tener al menos 12 caracteres.")
        if session_ttl_seconds < 60:
            raise ValueError("La sesión de operador debe durar al menos 60 segundos.")
        self._now = now
        self._ttl = session_ttl_seconds
        self._iterations = pbkdf2_iterations
        self._salt = secrets.token_bytes(16)
        self._access_digest = self._derive(access_code)
        self._signing_key = secrets.token_bytes(32)
        self._sessions: dict[str, OperatorSession] = {}
        self._failed_logins: list[float] = []
        self._lock = threading.Lock()

    def _derive(self, value: str) -> bytes:
        return hashlib.pbkdf2_hmac(
            "sha256",
            value.encode("utf-8"),
            self._salt,
            self._iterations,
        )

    def _sign(self, purpose: str, value: str) -> str:
        payload = base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii")
        signature = hmac.new(
            self._signing_key,
            f"{purpose}:{payload}".encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        return f"{payload}.{signature}"

    def _unsign(self, purpose: str, signed_value: str | None) -> str | None:
        try:
            payload, signature = str(signed_value or "").split(".", 1)
            expected = hmac.new(
                self._signing_key,
                f"{purpose}:{payload}".encode("ascii"),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                return None
            return base64.urlsafe_b64decode(payload.encode("ascii")).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None

    def issue_login_challenge(self) -> tuple[str, str]:
        expires_at = int(self._now()) + LOGIN_CHALLENGE_TTL_SECONDS
        token = secrets.token_urlsafe(24)
        return token, self._sign("login", f"{expires_at}:{token}")

    def validate_login_challenge(
        self, signed_cookie: str | None, submitted_token: str
    ) -> bool:
        value = self._unsign("login", signed_cookie)
        if value is None:
            return False
        try:
            expiry_text, expected_token = value.split(":", 1)
            return int(expiry_text) >= int(self._now()) and hmac.compare_digest(
                expected_token, submitted_token
            )
        except ValueError:
            return False

    def authenticate_result(self, access_code: str) -> str:
        now = self._now()
        with self._lock:
            self._failed_logins = [
                attempt for attempt in self._failed_logins if now - attempt < 300
            ]
            if len(self._failed_logins) >= 5:
                return "rate_limited"
        valid = hmac.compare_digest(self._derive(access_code), self._access_digest)
        with self._lock:
            if valid:
                self._failed_logins.clear()
            else:
                self._failed_logins.append(now)
        return "accepted" if valid else "invalid_code"

    def authenticate(self, access_code: str) -> bool:
        return self.authenticate_result(access_code) == "accepted"

    def create_session(self) -> tuple[OperatorSession, str]:
        session_id = secrets.token_urlsafe(32)
        session = OperatorSession(
            session_id=session_id,
            actor=self.actor,
            csrf_token=secrets.token_urlsafe(32),
            expires_at=int(self._now()) + self._ttl,
        )
        with self._lock:
            self._sessions[session_id] = session
        return session, self._sign("session", session_id)

    def get_session(self, signed_cookie: str | None) -> OperatorSession | None:
        session_id = self._unsign("session", signed_cookie)
        if session_id is None:
            return None
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if session.expires_at <= int(self._now()):
                self._sessions.pop(session_id, None)
                return None
            return session

    def select_company(
        self, signed_cookie: str | None, company_id: uuid.UUID,
        company_code: str, company_name: str,
    ) -> OperatorSession | None:
        session_id = self._unsign("session", signed_cookie)
        if session_id is None:
            return None
        with self._lock:
            current = self._sessions.get(session_id)
            if current is None or current.expires_at <= int(self._now()):
                self._sessions.pop(session_id, None)
                return None
            selected = OperatorSession(
                session_id=current.session_id, actor=current.actor,
                csrf_token=current.csrf_token, expires_at=current.expires_at,
                company_id=company_id, company_code=_require_text(company_code, "company_code"),
                company_name=_require_text(company_name, "company_name"),
            )
            self._sessions[session_id] = selected
            return selected

    def revoke(self, signed_cookie: str | None) -> None:
        session_id = self._unsign("session", signed_cookie)
        if session_id is not None:
            with self._lock:
                self._sessions.pop(session_id, None)


def _templates() -> Environment:
    template_dir = files("perfect_catalog").joinpath("templates")
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(("html", "xml")),
        undefined=StrictUndefined,
    )


def _render(environment: Environment, name: str, **context: Any) -> HTMLResponse:
    context.setdefault("session", None)
    context.setdefault("version", OPERATOR_VERSION)
    return HTMLResponse(environment.get_template(name).render(**context))


def _set_security_headers(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'self'; script-src 'self'; img-src 'self' blob:; "
        "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
    )
    # El login local necesita Referer como respaldo cuando una superficie Chromium
    # omite Origin. same-origin nunca lo divulga a otro origen.
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"


def _origin_tuple(value: str) -> tuple[str, str, int] | None:
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        origin_port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return None
    return parsed.scheme, parsed.hostname.lower(), origin_port


def _same_origin(request: Request) -> bool:
    expected = _origin_tuple(str(request.base_url))
    if expected is None or expected[1] not in {"127.0.0.1", "localhost", "testserver"}:
        return False
    origin = request.headers.get("origin")
    if origin:
        return _origin_tuple(origin) == expected
    # Chromium may omit Origin in constrained/local browser surfaces. A same-origin
    # Referer plus Fetch Metadata retains an explicit, browser-enforced CSRF boundary.
    referer = request.headers.get("referer")
    fetch_site = request.headers.get("sec-fetch-site", "").lower()
    return bool(
        referer
        and _origin_tuple(referer) == expected
        and fetch_site == "same-origin"
    )


async def _parse_form(request: Request) -> dict[str, str]:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip()
    if content_type != "application/x-www-form-urlencoded":
        raise ValueError("El formulario debe usar application/x-www-form-urlencoded.")
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_FORM_BYTES:
        raise ValueError("El formulario supera el tamaño permitido.")
    body = await request.body()
    if len(body) > MAX_FORM_BYTES:
        raise ValueError("El formulario supera el tamaño permitido.")
    values = parse_qs(
        body.decode("utf-8", errors="strict"),
        keep_blank_values=True,
        max_num_fields=32,
    )
    if any(len(items) != 1 for items in values.values()):
        raise ValueError("El formulario contiene campos duplicados.")
    return {key: items[0] for key, items in values.items()}


def _uuid(value: str, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"{label} no contiene un UUID válido.") from exc


def _human_size(value: int) -> str:
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if size < 1024 or unit == "GiB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    raise AssertionError("unreachable")


def _error(
    environment: Environment,
    status_code: int,
    title: str,
    detail: str,
    *,
    session: OperatorSession | None = None,
) -> HTMLResponse:
    response = _render(
        environment,
        "operator_error.html",
        title=title,
        detail=detail,
        session=session,
        version=OPERATOR_VERSION,
    )
    response.status_code = status_code
    return response


def _unexpected_error(
    environment: Environment,
    title: str,
    public_detail: str,
    operation: str,
    exc: Exception,
    *,
    session: OperatorSession | None = None,
) -> HTMLResponse:
    """Correlaciona un fallo inesperado sin exponer SQL, rutas, credenciales ni datos internos."""
    diagnostic_id = secrets.token_hex(6)
    LOGGER.exception(
        "%s diagnostic_id=%s error_type=%s sqlstate=%s",
        operation, diagnostic_id, type(exc).__name__, getattr(exc, "sqlstate", None),
    )
    return _error(
        environment, 503, title,
        f"{public_detail} Diagnóstico: {diagnostic_id}.",
        session=session,
    )


def create_operator_app(
    gateway: ReviewGateway,
    authenticator: OperatorAuthenticator,
    *,
    intake_root: Path | None = None,
    promotion_output_dir: Path | None = None,
    catalog_output_dir: Path | None = None,
    image_output_dir: Path | None = None,
    brand_asset_dir: Path | None = None,
) -> FastAPI:
    environment = _templates()
    resolved_intake_root = intake_root or Path("data/intake")
    resolved_promotion_output = promotion_output_dir or Path("data/exports/imports")
    resolved_catalog_output = catalog_output_dir or Path("data/exports/catalogs")
    resolved_image_output = image_output_dir or Path("data/images")
    resolved_brand_assets = brand_asset_dir or Path("data/brand-assets")
    intake_service = SecureIntakeService(resolved_intake_root, gateway)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        gateway.close()

    app = FastAPI(
        title="Perfect Catalog Operator",
        version=OPERATOR_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "testserver"],
    )
    static_dir = files("perfect_catalog").joinpath("static")
    app.mount(
        "/operator/static",
        StaticFiles(directory=str(static_dir), check_dir=True),
        name="operator-static",
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Callable[..., Any]) -> Response:
        response: Response
        match = re.match(
            r"^/operator/(?:(plans)/([0-9a-fA-F-]{36})(?:/.*)?|(catalogs)/([0-9a-fA-F-]{36})(?:/.*)?|brands/identity/([0-9a-fA-F-]{36})/logo|(intake)/([0-9a-fA-F-]{36})(?:/.*)?|images/(index|candidates)/([0-9a-fA-F-]{36})(?:/.*)?)$",
            request.url.path,
        )
        session = authenticator.get_session(request.cookies.get(SESSION_COOKIE))
        authorize = getattr(gateway, "authorize_company_resource", None)
        if match and session is not None and session.company_id is not None and authorize is not None:
            resource_type = (
                "plan" if match.group(1) else "release" if match.group(3)
                else "identity" if match.group(5) else "intake" if match.group(6)
                else "image_index" if match.group(8) == "index" else "image_candidate"
            )
            resource_text = (
                match.group(2) or match.group(4) or match.group(5)
                or match.group(7) or match.group(9)
            )
            try:
                allowed = await run_in_threadpool(
                    authorize, session.company_id, resource_type, uuid.UUID(resource_text),
                )
            except Exception as exc:
                response = _unexpected_error(
                    environment, "Contexto no disponible",
                    "No se pudo verificar que el recurso pertenezca a la empresa activa.",
                    "company_resource_guard_failed", exc, session=session,
                )
            else:
                response = await call_next(request) if allowed else _error(
                    environment, 404, "Recurso no encontrado",
                    "El recurso no existe dentro de la empresa activa.", session=session,
                )
        else:
            response = await call_next(request)
        _set_security_headers(response)
        return response

    def current_session(request: Request) -> OperatorSession | None:
        return authenticator.get_session(request.cookies.get(SESSION_COOKIE))

    def require_session(request: Request) -> OperatorSession | RedirectResponse:
        session = current_session(request)
        if session is None:
            return RedirectResponse("/operator/login", status_code=303)
        if session.company_id is None and hasattr(gateway, "companies"):
            return RedirectResponse("/operator/company", status_code=303)
        return session

    async def available_companies() -> list[dict[str, Any]]:
        method = getattr(gateway, "companies", None)
        if method is None:
            return []
        return await run_in_threadpool(method)

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse("/operator", status_code=303)

    @app.get("/operator/login", response_class=HTMLResponse)
    def login_page(request: Request) -> Response:
        if current_session(request) is not None:
            return RedirectResponse("/operator", status_code=303)
        challenge, signed_challenge = authenticator.issue_login_challenge()
        response = _render(
            environment,
            "operator_login.html",
            login_csrf=challenge,
            error=None,
            version=OPERATOR_VERSION,
        )
        response.set_cookie(
            LOGIN_COOKIE,
            signed_challenge,
            httponly=True,
            samesite="strict",
            secure=False,
            max_age=LOGIN_CHALLENGE_TTL_SECONDS,
            path=LOGIN_COOKIE_PATH,
        )
        response.delete_cookie(LOGIN_COOKIE, path="/operator/login")
        return response

    @app.post("/operator/login", response_class=HTMLResponse)
    async def login(request: Request) -> Response:
        try:
            form = await _parse_form(request)
            if set(form) != {"csrf_token", "access_code"}:
                raise ValueError("El formulario de login contiene campos ausentes o desconocidos.")
        except (ValueError, UnicodeDecodeError) as exc:
            return _error(environment, 400, "Formulario inválido", str(exc))
        valid_origin = _same_origin(request)
        valid_challenge = authenticator.validate_login_challenge(
            request.cookies.get(LOGIN_COOKIE), form.get("csrf_token", "")
        )
        authentication_result = "not_checked"
        if valid_origin and valid_challenge:
            authentication_result = await run_in_threadpool(
                authenticator.authenticate_result, form.get("access_code", "")
            )
        if not valid_origin:
            rejection = (
                "Origen local no verificado. Abre esta misma dirección de login y reintenta."
            )
        elif not valid_challenge:
            rejection = (
                "Sesión de login vencida o cookie de challenge no disponible. "
                "Recarga esta página antes de reintentar."
            )
        elif authentication_result == "rate_limited":
            rejection = "Demasiados intentos fallidos. Espera cinco minutos antes de reintentar."
        else:
            rejection = "El código temporal no coincide con el definido al iniciar el servidor."
        if not (valid_origin and valid_challenge and authentication_result == "accepted"):
            challenge, signed_challenge = authenticator.issue_login_challenge()
            response = _render(
                environment,
                "operator_login.html",
                login_csrf=challenge,
                error=rejection,
                version=OPERATOR_VERSION,
            )
            response.status_code = 401
            response.set_cookie(
                LOGIN_COOKIE,
                signed_challenge,
                httponly=True,
                samesite="strict",
                secure=False,
                max_age=LOGIN_CHALLENGE_TTL_SECONDS,
                path=LOGIN_COOKIE_PATH,
            )
            response.delete_cookie(LOGIN_COOKIE, path="/operator/login")
            return response
        _, signed_session = authenticator.create_session()
        destination = "/operator"
        try:
            companies = await available_companies()
            usable = [company for company in companies if company.get("is_active", True)]
            if len(usable) == 1:
                company = usable[0]
                authenticator.select_company(
                    signed_session, _uuid(str(company["company_id"]), "company_id"),
                    str(company["code"]), str(company["display_name"]),
                )
            elif usable:
                destination = "/operator/company"
        except Exception as exc:
            LOGGER.exception("No se pudo cargar Company durante login: %s", exc)
            destination = "/operator/company"
        response = RedirectResponse(destination, status_code=303)
        response.delete_cookie(LOGIN_COOKIE, path=LOGIN_COOKIE_PATH)
        response.delete_cookie(LOGIN_COOKIE, path="/operator/login")
        response.set_cookie(
            SESSION_COOKIE,
            signed_session,
            httponly=True,
            samesite="strict",
            secure=False,
            max_age=SESSION_TTL_SECONDS,
            path="/operator",
        )
        return response

    @app.get("/operator/company", response_class=HTMLResponse)
    async def company_page(request: Request) -> Response:
        session = current_session(request)
        if session is None:
            return RedirectResponse("/operator/login", status_code=303)
        try:
            companies = await available_companies()
        except Exception as exc:
            return _unexpected_error(
                environment, "Empresas no disponibles",
                "No se pudo cargar el contexto de trabajo. Revisa PostgreSQL.",
                "company_context_read_failed", exc, session=session,
            )
        return _render(
            environment, "operator_company.html", companies=companies,
            session=session, version=OPERATOR_VERSION,
        )

    @app.post("/operator/company")
    async def select_company_route(request: Request) -> Response:
        session = current_session(request)
        if session is None:
            return RedirectResponse("/operator/login", status_code=303)
        try:
            form = await _parse_form(request)
            if set(form) != {"csrf_token", "company_id"}:
                raise ValueError("El selector contiene campos ausentes o desconocidos.")
            if not _same_origin(request) or not hmac.compare_digest(
                form["csrf_token"], session.csrf_token
            ):
                return _error(environment, 403, "Solicitud rechazada", "La evidencia CSRF no coincide.", session=session)
            requested_id = _uuid(form["company_id"], "company_id")
            companies = await available_companies()
            selected = next(
                (company for company in companies
                 if str(company["company_id"]) == str(requested_id) and company.get("is_active", True)),
                None,
            )
            if selected is None:
                raise PermissionError("La empresa no existe o no está activa.")
            if authenticator.select_company(
                request.cookies.get(SESSION_COOKIE), requested_id,
                str(selected["code"]), str(selected["display_name"]),
            ) is None:
                return RedirectResponse("/operator/login", status_code=303)
        except (ValueError, PermissionError) as exc:
            return _error(environment, 409, "Empresa no seleccionada", str(exc), session=session)
        return RedirectResponse("/operator", status_code=303)

    @app.post("/operator/logout")
    async def logout(request: Request) -> Response:
        session = current_session(request)
        if session is None:
            return RedirectResponse("/operator/login", status_code=303)
        try:
            form = await _parse_form(request)
        except (ValueError, UnicodeDecodeError) as exc:
            return _error(environment, 400, "Formulario inválido", str(exc), session=session)
        if not _same_origin(request) or not hmac.compare_digest(
            form.get("csrf_token", ""), session.csrf_token
        ):
            return _error(environment, 403, "Solicitud rechazada", "La evidencia CSRF no coincide.", session=session)
        authenticator.revoke(request.cookies.get(SESSION_COOKIE))
        response = RedirectResponse("/operator/login", status_code=303)
        response.delete_cookie(SESSION_COOKIE, path="/operator")
        return response

    @app.get("/operator", response_class=HTMLResponse)
    async def dashboard(request: Request) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        try:
            plans = await run_in_threadpool(
                gateway.plans, limit=100, company_id=session_or_redirect.company_id,
            )
            intakes = await run_in_threadpool(
                gateway.intake_submissions, kind="all", status="all", limit=1, offset=0,
                company_id=session_or_redirect.company_id,
            )
            image_summary = await run_in_threadpool(
                gateway.image_candidates, limit=1, offset=0,
                company_id=session_or_redirect.company_id,
            )
            releases = await run_in_threadpool(
                gateway.catalog_releases, limit=100, company_id=session_or_redirect.company_id,
            )
        except Exception as exc:
            return _unexpected_error(
                environment, "PostgreSQL no disponible",
                "No se pudo leer la cola. Revisa la consola del servidor operador.",
                "dashboard_read_failed", exc, session=session_or_redirect,
            )
        return _render(
            environment,
            "operator_plans.html",
            plans=plans,
            workflow={
                "intake_count": int(intakes["filtered_count"]),
                "pending_review_count": sum(int(plan["pending_count"]) for plan in plans),
                "pending_image_count": int(image_summary["pending_count"]),
                "materialize_image_count": int(image_summary["approved_unmaterialized_count"]),
                "draft_release_count": sum(release["status"] == "draft" for release in releases),
                "published_release_count": sum(release["status"] == "published" for release in releases),
            },
            session=session_or_redirect,
            version=OPERATOR_VERSION,
        )

    @app.get("/operator/intake", response_class=HTMLResponse)
    async def intake_page(
        request: Request,
        kind: str = "all",
        status: str = "all",
        page: int = 1,
    ) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        try:
            if page < 1 or page > 100_000:
                raise ValueError("Página fuera del rango permitido.")
            limit = 50
            submissions = await run_in_threadpool(
                intake_service.list,
                kind=kind,
                status=status,
                limit=limit,
                offset=(page - 1) * limit,
                company_id=session_or_redirect.company_id,
            )
        except ValueError as exc:
            return _error(
                environment,
                400,
                "Filtro inválido",
                str(exc),
                session=session_or_redirect,
            )
        except Exception as exc:
            return _unexpected_error(
                environment, "PostgreSQL no disponible",
                "No se pudo leer el historial de ingresos. Revisa la consola del servidor operador.",
                "intake_history_read_failed", exc, session=session_or_redirect,
            )
        for submission in submissions["items"]:
            submission["size_label"] = _human_size(submission["size_bytes"])
            submitted_at = submission["submitted_at"]
            submission["submitted_label"] = (
                submitted_at.strftime("%Y-%m-%d %H:%M UTC")
                if hasattr(submitted_at, "strftime")
                else str(submitted_at)
            )
        result = request.query_params.get("result")
        message = {
            "quarantined": (
                "Archivo validado y guardado en cuarentena. "
                "No fue importado ni publicado."
            ),
            "duplicate": (
                "Contenido duplicado reconocido. "
                "Se conservó el nuevo evento sin copiar los bytes."
            ),
            "rejected": "Archivo rechazado por el validador. No se conservaron sus bytes.",
            "promoted": "Ingreso perfilado; el dry-run quedó pendiente de revisión.",
            "already_promoted": "Este ingreso ya tenía un dry-run enlazado.",
            "indexed": "ZIP indexado sin extracción. Las asociaciones permanecen pendientes de revisión.",
            "already_indexed": "Este ZIP ya tenía un índice verificable; no se duplicó.",
        }.get(result)
        query_args = {"kind": kind, "status": status}
        previous_url = (
            f"/operator/intake?{urlencode({**query_args, 'page': page - 1})}"
            if page > 1
            else None
        )
        next_url = (
            f"/operator/intake?{urlencode({**query_args, 'page': page + 1})}"
            if page * limit < submissions["filtered_count"]
            else None
        )
        return _render(
            environment,
            "operator_intake.html",
            submissions=submissions,
            kinds=intake_kind_options(),
            kind_labels={
                key: value["label"] for key, value in INTAKE_KINDS.items()
            },
            selected_kind=kind,
            selected_status=status,
            page=page,
            previous_url=previous_url,
            next_url=next_url,
            message=message,
            request_result=result,
            session=session_or_redirect,
            version=OPERATOR_VERSION,
        )

    @app.get("/operator/catalogs", response_class=HTMLResponse)
    async def catalogs_page(request: Request) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        try:
            releases = await run_in_threadpool(
                gateway.catalog_releases, limit=100, company_id=session_or_redirect.company_id,
            )
            plans = await run_in_threadpool(
                gateway.plans, limit=100, company_id=session_or_redirect.company_id,
            )
            exports = await run_in_threadpool(
                list_operator_catalog_exports, resolved_catalog_output, limit=100
            )
            preflight_receipts = await run_in_threadpool(
                list_indesign_preflight_receipts, resolved_catalog_output, limit=500
            )
        except Exception as exc:
            return _unexpected_error(
                environment, "Catálogos no disponibles",
                "No se pudieron leer publicaciones o exportaciones. Revisa la consola del servidor.",
                "catalog_workspace_read_failed", exc, session=session_or_redirect,
            )
        message = {
            "created": "Catálogo generado y verificado. Ya puedes descargar sus entregables.",
            "built": "Borrador inmutable construido. Revisa su checksum antes de publicarlo.",
            "already_built": "El borrador exacto ya existía; no se duplicó.",
            "published": "Release publicado. Ya está habilitado para exportación.",
            "already_published": "El release exacto ya estaba publicado.",
            "preflight_recorded": "Preflight InDesign validado y asociado a la exportación exacta.",
        }.get(request.query_params.get("result"))
        preflight_by_export: dict[str, dict[str, Any]] = {}
        for receipt in preflight_receipts:
            export_key = str(receipt["export_id"])
            current = preflight_by_export.get(export_key)
            if current is None or str(receipt["received_at"]) > str(current["received_at"]):
                preflight_by_export[export_key] = receipt
        return _render(
            environment,
            "operator_catalogs.html",
            releases=releases,
            plans=plans,
            exports=exports,
            preflight_by_export=preflight_by_export,
            formats=SUPPORTED_FORMATS,
            indesign_templates=INDESIGN_TEMPLATE_PROFILES,
            message=message,
            session=session_or_redirect,
            version=OPERATOR_VERSION,
        )

    @app.get("/operator/brands", response_class=HTMLResponse)
    async def brands_page(request: Request) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        try:
            profiles = await run_in_threadpool(
                gateway.brand_profiles, company_id=session_or_redirect.company_id,
            )
            identities = await run_in_threadpool(
                gateway.visual_identities, company_id=session_or_redirect.company_id,
            )
        except Exception as exc:
            return _unexpected_error(
                environment, "Marcas no disponibles",
                "Ejecuta ACTUALIZAR-SISTEMA.cmd o revisa PostgreSQL.",
                "brand_workspace_read_failed", exc, session=session_or_redirect,
            )
        message = {"created": "Marca creada. Ya está disponible como perfil visual.", "identity_created": "Logo y colores guardados como una nueva revisión auditada."}.get(request.query_params.get("result"))
        return _render(
            environment, "operator_brands.html", profiles=profiles, identities=identities, message=message,
            session=session_or_redirect, version=OPERATOR_VERSION,
        )

    @app.post("/operator/brands/identity")
    async def create_visual_identity_route(request: Request) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse): return session_or_redirect
        session = session_or_redirect
        try:
            content_length = int(request.headers.get("content-length") or 0)
            if not 0 < content_length <= 6 * 1024 * 1024: raise ValueError("La carga supera el límite permitido.")
            async with request.form(max_files=1, max_fields=12, max_part_size=5 * 1024 * 1024 + 1) as form:
                expected = {"csrf_token","scope","brand_profile_id","vehicle_make_id","display_name","primary_color","secondary_color","ink_color","paper_color","reason","confirm","logo"}
                if set(form) not in (expected, expected - {"logo"}): raise ValueError("El formulario contiene campos ausentes o desconocidos.")
                if not _same_origin(request) or not hmac.compare_digest(str(form["csrf_token"]), session.csrf_token):
                    return _error(environment, 403, "Solicitud rechazada", "La evidencia CSRF no coincide.", session=session)
                if str(form["confirm"]) != "yes": raise ValueError("Debes confirmar la identidad visual.")
                upload = form.get("logo")
                if upload is not None and not isinstance(upload, UploadFile): raise ValueError("El logo no es un archivo válido.")
                content = await upload.read(5 * 1024 * 1024 + 1) if isinstance(upload, UploadFile) else None
                scope = str(form["scope"])
                profile_id = _uuid(str(form["brand_profile_id"]), "brand_profile_id") if scope == "brand" else None
                vehicle_make_id = _uuid(str(form["vehicle_make_id"]), "vehicle_make_id") if scope == "vehicle_make" else None
                await run_in_threadpool(
                    gateway.create_visual_identity,
                    scope=scope,
                    company_id=session.company_id if scope == "company" else None,
                    brand_profile_id=profile_id,
                    vehicle_make_id=vehicle_make_id,
                    display_name=str(form["display_name"]), colors={key: str(form[key]) for key in ("primary_color","secondary_color","ink_color","paper_color")},
                    filename=str(upload.filename or "logo") if isinstance(upload, UploadFile) else None,
                    content=content, actor=session.actor,
                    reason=str(form["reason"]), asset_root=resolved_brand_assets,
                )
        except (ValueError, RuntimeError, PermissionError) as exc:
            return _error(environment, 409, "Identidad no guardada", str(exc), session=session)
        except Exception:
            diagnostic_id = uuid.uuid4().hex[:12]; LOGGER.exception("Fallo de identidad visual; diagnostico=%s", diagnostic_id)
            return _error(environment, 503, "Identidad no disponible", f"No se guardó. Diagnóstico: {diagnostic_id}.", session=session)
        return RedirectResponse("/operator/brands?result=identity_created", status_code=303)

    @app.get("/operator/brands/identity/{revision_id}/logo")
    async def visual_identity_logo(request: Request, revision_id: str) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse): return session_or_redirect
        try:
            target, media_type = await run_in_threadpool(
                gateway.visual_identity_asset, _uuid(revision_id, "revision_id"), resolved_brand_assets,
            )
        except (ValueError, FileNotFoundError):
            return _error(environment, 404, "Logo no disponible", "El activo no existe o no supera SHA-256.", session=session_or_redirect)
        return FileResponse(target, media_type=media_type)

    @app.post("/operator/brands")
    async def create_brand_route(request: Request) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        session = session_or_redirect
        profile_fields = {
            "code", "display_name", "tagline", "primary_color", "secondary_color",
            "ink_color", "paper_color", "public_base_url",
        }
        try:
            form = await _parse_form(request)
            if set(form) != profile_fields | {"csrf_token", "reason", "confirm"}:
                raise ValueError("El formulario contiene campos ausentes o desconocidos.")
            if not _same_origin(request) or not hmac.compare_digest(form["csrf_token"], session.csrf_token):
                return _error(environment, 403, "Solicitud rechazada", "La evidencia CSRF no coincide.", session=session)
            if form["confirm"] != "yes":
                raise ValueError("Debes confirmar la creacion del perfil de marca.")
            reason = _require_text(form["reason"], "reason")
            await run_in_threadpool(
                gateway.create_brand_profile,
                {key: form[key] for key in profile_fields}, session.actor, reason,
                session.company_id,
            )
        except (ValueError, RuntimeError, PermissionError) as exc:
            return _error(environment, 409, "Marca no creada", str(exc), session=session)
        except Exception as exc:
            return _unexpected_error(environment, "Marca no creada", "PostgreSQL no guardó el perfil. Revisa la consola.", "brand_create_failed", exc, session=session)
        return RedirectResponse("/operator/brands?result=created", status_code=303)

    @app.post("/operator/catalogs/releases")
    async def build_catalog_release_route(request: Request) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        session = session_or_redirect
        try:
            form = await _parse_form(request)
            if set(form) != {"csrf_token", "plan_id", "fingerprint", "version", "brand", "reason", "confirm"}:
                raise ValueError("El formulario contiene campos ausentes o desconocidos.")
            if not _same_origin(request) or not hmac.compare_digest(form["csrf_token"], session.csrf_token):
                return _error(environment, 403, "Solicitud rechazada", "La evidencia CSRF no coincide.", session=session)
            if form["confirm"] != "yes":
                raise ValueError("Debes confirmar la construcción del borrador inmutable.")
            reason = _require_text(form["reason"], "reason")
            if not 4 <= len(reason) <= MAX_REASON_LENGTH:
                raise ValueError("reason debe contener entre 4 y 500 caracteres.")
            brand = _require_text(form["brand"], "brand")
            if len(brand) > 120:
                raise ValueError("brand no puede superar 120 caracteres.")
            result = await run_in_threadpool(
                gateway.build_catalog_release,
                _uuid(form["plan_id"], "plan_id"),
                form["fingerprint"], form["version"], session.actor, reason, brand,
            )
        except (ValueError, RuntimeError, PermissionError, NotImplementedError) as exc:
            return _error(environment, 409, "Release no construido", str(exc), session=session)
        except Exception:
            diagnostic_id = uuid.uuid4().hex[:12]
            LOGGER.exception("Fallo al construir release; diagnostico=%s", diagnostic_id)
            return _error(
                environment, 503, "Construcción no disponible",
                f"No se creó el release. Diagnóstico: {diagnostic_id}.", session=session,
            )
        return RedirectResponse(
            f"/operator/catalogs?{urlencode({'result': str(result['status'])})}", status_code=303
        )

    @app.get("/operator/catalogs/{release_id}/products")
    async def catalog_release_products_route(
        request: Request, release_id: str, query: str = "", limit: int = 24, offset: int = 0,
    ) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        try:
            result = await run_in_threadpool(
                gateway.catalog_release_products, _uuid(release_id, "release_id"),
                query=query, limit=limit, offset=offset,
            )
        except (ValueError, RuntimeError, PermissionError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        except Exception as exc:
            diagnostic_id = secrets.token_hex(6)
            LOGGER.exception(
                "catalog_product_picker_failed diagnostic_id=%s error_type=%s sqlstate=%s",
                diagnostic_id, type(exc).__name__, getattr(exc, "sqlstate", None),
            )
            return JSONResponse(
                {"error": "No se pudieron consultar los productos.", "diagnostic_id": diagnostic_id},
                status_code=503,
            )
        return JSONResponse(result)

    @app.get("/operator/catalogs/{release_id}/preview", response_class=HTMLResponse)
    async def preview_catalog_release_route(
        request: Request, release_id: str, group_by: str = "category_path",
        group_by_secondary: str = "", filter_field: str = "all",
        filter_query: str = "", columns: int = 2, theme: str = "forest",
        preview_target: str = "digital", template_profile: str = "T4",
        title: str = "", subtitle: str = "", selected_references: str = "",
        show_category: bool = True, show_brand: bool = True, show_oem: bool = True,
        show_applications: bool = True, show_engine: bool = True,
    ) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        try:
            if columns not in {1, 2, 3}:
                raise ValueError("La cantidad de columnas no es válida.")
            if theme not in CATALOG_THEMES:
                raise ValueError("Tema editorial no soportado.")
            if preview_target not in {"digital", "indesign"}:
                raise ValueError("Destino de vista previa no soportado.")
            template_profile = template_profile.upper()
            if template_profile not in INDESIGN_TEMPLATE_PROFILES:
                raise ValueError("Perfil InDesign no soportado.")
            if group_by not in {"category_path", "brand", "vehicle_make", "internal_reference_original"}:
                raise ValueError("Agrupación no permitida.")
            if group_by_secondary not in {"", "category_path", "brand", "vehicle_make", "internal_reference_original"}:
                raise ValueError("Agrupación secundaria no permitida.")
            if filter_field not in {"all", "category_path", "brand", "internal_reference_original", "name_original"}:
                raise ValueError("Campo de filtro no permitido.")
            if len(filter_query) > 120:
                raise ValueError("El filtro no puede superar 120 caracteres.")
            title = title.strip()
            subtitle = subtitle.strip()
            if len(title) > 120 or len(subtitle) > 180:
                raise ValueError("Título o subtítulo demasiado largo.")
            if len(selected_references) > 20000:
                raise ValueError("La lista manual de referencias es demasiado larga.")
            preview = await run_in_threadpool(
                gateway.preview_catalog_release,
                _uuid(release_id, "release_id"), group_by=group_by,
                group_by_secondary=group_by_secondary, filter_field=filter_field,
                filter_query=filter_query, selected_references=selected_references, sample_limit=24,
            )
            title = title or f"Catálogo {preview['release']['version']}"
            layout_estimate = estimate_indesign_layout(preview["groups"], template_profile)
        except (ValueError, RuntimeError, PermissionError) as exc:
            return _error(environment, 400, "Vista previa no disponible", str(exc), session=session_or_redirect)
        except Exception as exc:
            return _unexpected_error(environment, "Vista previa no disponible", "No se pudo leer el release publicado.", "catalog_preview_failed", exc, session=session_or_redirect)
        return _render(
            environment, "operator_catalog_preview.html",
            preview=preview, columns=columns, theme=theme, themes=CATALOG_THEMES,
            preview_target=preview_target, template_profile=template_profile,
            layout_estimate=layout_estimate,
            title=title, subtitle=subtitle,
            show_category=show_category, show_brand=show_brand, show_oem=show_oem,
            show_applications=show_applications, show_engine=show_engine,
            session=session_or_redirect,
            version=OPERATOR_VERSION,
        )

    @app.get("/operator/catalogs/{release_id}/preview/images/{item_number}")
    async def catalog_preview_image_route(
        request: Request, release_id: str, item_number: int,
    ) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        try:
            target = await run_in_threadpool(
                gateway.catalog_preview_image,
                _uuid(release_id, "release_id"), item_number, resolved_image_output,
            )
        except (ValueError, FileNotFoundError, RuntimeError):
            return _error(
                environment, 404, "Imagen no disponible",
                "La imagen no pertenece a este release o no supera su verificación.",
                session=session_or_redirect,
            )
        return FileResponse(target, filename=target.name)

    @app.post("/operator/catalogs/{release_id}/publish")
    async def publish_catalog_release_route(request: Request, release_id: str) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        session = session_or_redirect
        try:
            form = await _parse_form(request)
            if set(form) != {"csrf_token", "snapshot_sha256", "reason", "confirm"}:
                raise ValueError("El formulario contiene campos ausentes o desconocidos.")
            if not _same_origin(request) or not hmac.compare_digest(form["csrf_token"], session.csrf_token):
                return _error(environment, 403, "Solicitud rechazada", "La evidencia CSRF no coincide.", session=session)
            if form["confirm"] != "yes":
                raise ValueError("Debes confirmar la publicación del checksum exacto.")
            reason = _require_text(form["reason"], "reason")
            if not 4 <= len(reason) <= MAX_REASON_LENGTH:
                raise ValueError("reason debe contener entre 4 y 500 caracteres.")
            result = await run_in_threadpool(
                gateway.publish_catalog_release,
                _uuid(release_id, "release_id"), form["snapshot_sha256"], session.actor, reason,
            )
        except (ValueError, RuntimeError, PermissionError, NotImplementedError) as exc:
            return _error(environment, 409, "Release no publicado", str(exc), session=session)
        except Exception as exc:
            return _unexpected_error(environment, "Publicación no disponible", "No se publicó el release. Revisa la consola del servidor.", "catalog_publish_failed", exc, session=session)
        return RedirectResponse(
            f"/operator/catalogs?{urlencode({'result': str(result['status'])})}", status_code=303
        )

    @app.post("/operator/catalogs/{release_id}/exports")
    async def create_catalog_export(request: Request, release_id: str) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        session = session_or_redirect
        try:
            form = await _parse_form(request)
            allowed_fields = {
                "csrf_token", "title", "subtitle", "group_by", "group_by_secondary",
                "filter_field", "filter_query", "columns", "template_profile",
                "selected_references", "theme",
                "show_category", "show_brand", "show_oem", "show_applications", "show_engine",
                "format_html", "format_html_standalone", "format_pdf", "format_pptx", "format_indesign_json", "confirm",
            }
            if set(form) != allowed_fields:
                raise ValueError("El formulario contiene campos ausentes o desconocidos.")
            if not _same_origin(request) or not hmac.compare_digest(
                form.get("csrf_token", ""), session.csrf_token
            ):
                return _error(environment, 403, "Solicitud rechazada", "La evidencia CSRF no coincide.", session=session)
            if form["confirm"] != "yes":
                raise ValueError("Debes confirmar la exportación del release publicado.")
            title = _require_text(form["title"], "title")
            subtitle = form["subtitle"].strip()
            group_by = form["group_by"].strip()
            if len(title) > 120 or len(subtitle) > 180:
                raise ValueError("Título o subtítulo demasiado largo.")
            if group_by not in {"category_path", "brand", "vehicle_make", "internal_reference_original"}:
                raise ValueError("Agrupación no permitida.")
            group_by_secondary = form["group_by_secondary"].strip()
            if group_by_secondary not in {"", "category_path", "brand", "vehicle_make", "internal_reference_original"}:
                raise ValueError("Agrupación secundaria no permitida.")
            filter_field = form["filter_field"].strip()
            if filter_field not in {"all", "category_path", "brand", "internal_reference_original", "name_original"}:
                raise ValueError("Campo de filtro no permitido.")
            filter_query = form["filter_query"].strip()
            if len(filter_query) > 120:
                raise ValueError("El filtro no puede superar 120 caracteres.")
            selected_references = form["selected_references"].strip()
            if len(selected_references) > 20000:
                raise ValueError("La lista manual de referencias es demasiado larga.")
            visibility = {}
            for field in ("show_category", "show_brand", "show_oem", "show_applications", "show_engine"):
                if form[field] not in {"yes", "no"}:
                    raise ValueError("La visibilidad de campos no es válida.")
                visibility[field] = form[field] == "yes"
            columns = int(form["columns"])
            if columns not in {1, 2, 3}:
                raise ValueError("La cantidad de columnas no es válida.")
            template_profile = form["template_profile"].upper()
            if template_profile not in INDESIGN_TEMPLATE_PROFILES:
                raise ValueError("Perfil InDesign no soportado.")
            theme = form["theme"].lower()
            if theme not in CATALOG_THEMES:
                raise ValueError("Tema editorial no soportado.")
            selected_formats = tuple(
                output_format for field, output_format in (
                    ("format_html", "html"),
                    ("format_html_standalone", "html-standalone"),
                    ("format_pdf", "pdf"),
                    ("format_pptx", "pptx"),
                    ("format_indesign_json", "indesign-json"),
                ) if form[field] == "yes"
            )
            if not selected_formats:
                raise ValueError("Selecciona al menos un formato.")
            parsed_release_id = _uuid(release_id, "release_id")
            await run_in_threadpool(
                gateway.export_catalog,
                parsed_release_id,
                resolved_catalog_output,
                formats=selected_formats,
                image_root=resolved_image_output,
                brand_asset_root=resolved_brand_assets,
                export_config={
                    "title": title,
                    "subtitle": subtitle,
                    "group_by": group_by,
                    "group_by_secondary": group_by_secondary,
                    "filter_field": filter_field,
                    "filter_query": filter_query,
                    "selected_references": selected_references,
                    "columns_per_row": columns,
                    "template_profile": template_profile,
                    "theme": theme,
                    **visibility,
                },
            )
        except (ValueError, RuntimeError, PermissionError, FileExistsError) as exc:
            return _error(environment, 409, "Exportación no creada", str(exc), session=session)
        except Exception as exc:
            return _unexpected_error(environment, "Exportación no disponible", "No se generaron entregables. Revisa la consola del servidor operador.", "catalog_export_failed", exc, session=session)
        return RedirectResponse("/operator/catalogs?result=created", status_code=303)

    @app.post("/operator/catalogs/{release_id}/exports/{export_id}/preflight")
    async def upload_indesign_preflight(
        request: Request, release_id: str, export_id: str,
    ) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        session = session_or_redirect
        if not _same_origin(request):
            return _error(environment, 403, "Solicitud rechazada", "El origen de la carga no coincide.", session=session)
        content_type = request.headers.get("content-type", "")
        if not content_type.lower().startswith("multipart/form-data;"):
            return _error(environment, 415, "Formulario inválido", "El preflight debe cargarse como multipart/form-data.", session=session)
        try:
            content_length = int(request.headers.get("content-length", ""))
        except ValueError:
            content_length = 0
        if content_length <= 0 or content_length > MAX_INDESIGN_PREFLIGHT_BYTES + 64 * 1024:
            return _error(environment, 413, "Preflight demasiado grande", "La carga supera el límite permitido de 1 MiB.", session=session)
        try:
            async with request.form(max_files=1, max_fields=4, max_part_size=MAX_INDESIGN_PREFLIGHT_BYTES + 1) as form:
                expected = {"csrf_token", "reason", "confirm", "file"}
                if set(form.keys()) != expected or any(len(form.getlist(field)) != 1 for field in expected):
                    raise ValueError("El formulario contiene campos ausentes, desconocidos o duplicados.")
                upload = form.getlist("file")[0]
                if not isinstance(upload, UploadFile) or not str(upload.filename or "").lower().endswith(".json"):
                    raise ValueError("Selecciona exactamente un archivo preflight.json.")
                if not hmac.compare_digest(str(form.get("csrf_token") or ""), session.csrf_token):
                    return _error(environment, 403, "Solicitud rechazada", "La evidencia CSRF no coincide.", session=session)
                if form.get("confirm") != "yes":
                    raise ValueError("Debes confirmar la asociación al release y exportación exactos.")
                reason = _require_text(str(form.get("reason") or ""), "reason")
                if not 4 <= len(reason) <= MAX_REASON_LENGTH:
                    raise ValueError("reason debe contener entre 4 y 500 caracteres.")
                content = await upload.read(MAX_INDESIGN_PREFLIGHT_BYTES + 1)
                await run_in_threadpool(
                    record_indesign_preflight, resolved_catalog_output,
                    _uuid(release_id, "release_id"), _uuid(export_id, "export_id"), content,
                    actor=session.actor, reason=reason,
                )
        except StarletteHTTPException:
            return _error(environment, 400, "Formulario inválido", "La estructura multipart no es válida.", session=session)
        except (ValueError, RuntimeError, PermissionError, FileNotFoundError) as exc:
            return _error(environment, 422, "Preflight rechazado", str(exc), session=session)
        except Exception as exc:
            return _unexpected_error(environment, "Preflight no disponible", "El reporte no quedó registrado.", "indesign_preflight_record_failed", exc, session=session)
        return RedirectResponse("/operator/catalogs?result=preflight_recorded", status_code=303)

    @app.get("/operator/catalogs/{release_id}/exports/{export_id}/{filename}")
    async def download_catalog_export(
        request: Request, release_id: str, export_id: str, filename: str
    ) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        try:
            target = await run_in_threadpool(
                resolve_catalog_download,
                resolved_catalog_output,
                _uuid(release_id, "release_id"),
                _uuid(export_id, "export_id"),
                filename,
            )
        except (ValueError, PermissionError, FileNotFoundError):
            return _error(environment, 404, "Archivo no encontrado", "La descarga no pertenece a una exportación válida.", session=session_or_redirect)
        return FileResponse(target, filename=target.name, media_type="application/octet-stream")

    @app.get("/operator/catalogs/{release_id}/exports/{export_id}/preflights/{receipt_id}")
    async def download_indesign_preflight_receipt(
        request: Request, release_id: str, export_id: str, receipt_id: str,
    ) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        try:
            target = await run_in_threadpool(
                resolve_indesign_preflight_receipt, resolved_catalog_output,
                _uuid(release_id, "release_id"), _uuid(export_id, "export_id"),
                _uuid(receipt_id, "receipt_id"),
            )
        except (ValueError, PermissionError, FileNotFoundError):
            return _error(environment, 404, "Recibo no encontrado", "El preflight no pertenece a esta exportación.", session=session_or_redirect)
        return FileResponse(target, filename=f"indesign-preflight-{receipt_id}.json", media_type="application/json")

    @app.post("/operator/intake")
    async def submit_intake(request: Request) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        session = session_or_redirect
        if not _same_origin(request):
            return _error(
                environment,
                403,
                "Solicitud rechazada",
                "El origen de la carga no coincide.",
                session=session,
            )
        content_type = request.headers.get("content-type", "")
        if not content_type.lower().startswith("multipart/form-data;"):
            return _error(
                environment,
                415,
                "Formulario inválido",
                "La carga debe usar multipart/form-data.",
                session=session,
            )
        try:
            content_length = int(request.headers.get("content-length", ""))
        except ValueError:
            return _error(
                environment,
                411,
                "Longitud requerida",
                "La carga debe declarar un tamaño válido.",
                session=session,
            )
        if content_length <= 0 or content_length > MAX_UPLOAD_REQUEST_BYTES:
            return _error(
                environment,
                413,
                "Carga demasiado grande",
                "La solicitud supera el límite global de 2 GiB.",
                session=session,
            )
        try:
            async with request.form(
                max_files=1, max_fields=5, max_part_size=MAX_FORM_BYTES
            ) as form:
                expected_fields = {"csrf_token", "kind", "reason", "confirm", "file"}
                if set(form.keys()) != expected_fields or any(
                    len(form.getlist(field)) != 1 for field in expected_fields
                ):
                    raise ValueError(
                        "El formulario contiene campos ausentes, desconocidos o duplicados."
                    )
                upload = form.getlist("file")[0]
                if not isinstance(upload, UploadFile):
                    raise ValueError("Debes seleccionar exactamente un archivo.")
                if not hmac.compare_digest(
                    str(form.get("csrf_token") or ""), session.csrf_token
                ):
                    return _error(
                        environment,
                        403,
                        "Solicitud rechazada",
                        "La evidencia CSRF no coincide.",
                        session=session,
                    )
                if form.get("confirm") != "yes":
                    raise ValueError(
                        "Debes confirmar que la carga no ejecuta una importación."
                    )
                submitted = await run_in_threadpool(
                    intake_service.submit,
                    upload.file,
                    filename=upload.filename,
                    claimed_media_type=upload.content_type,
                    kind=str(form.get("kind") or ""),
                    actor=session.actor,
                    reason=str(form.get("reason") or ""),
                    company_id=session.company_id,
                )
        except StarletteHTTPException:
            return _error(
                environment,
                400,
                "Formulario inválido",
                "La estructura multipart de la carga no es válida.",
                session=session,
            )
        except (ValueError, RuntimeError) as exc:
            return _error(
                environment,
                422,
                "Carga no aceptada",
                str(exc),
                session=session,
            )
        except Exception as exc:
            return _unexpected_error(environment, "Ingreso no disponible", "El archivo no quedó registrado. Revisa la consola del servidor operador.", "intake_submit_failed", exc, session=session)
        result = str(submitted["validation_status"])
        if submitted.get("duplicate_content"):
            result = "duplicate"
        return RedirectResponse(
            f"/operator/intake?{urlencode({'result': result})}", status_code=303
        )

    @app.post("/operator/intake/{submission_id}/promote")
    async def promote_intake(request: Request, submission_id: str) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        session = session_or_redirect
        try:
            form = await _parse_form(request)
            if set(form) != {"csrf_token", "reason", "confirm"}:
                raise ValueError("El formulario contiene campos ausentes o desconocidos.")
            if not _same_origin(request) or not hmac.compare_digest(
                form.get("csrf_token", ""), session.csrf_token
            ):
                return _error(environment, 403, "Solicitud rechazada", "La evidencia CSRF no coincide.", session=session)
            reason = _require_text(form.get("reason", ""), "reason")
            if not 4 <= len(reason) <= MAX_REASON_LENGTH:
                raise ValueError("reason debe contener entre 4 y 500 caracteres.")
            if form.get("confirm") != "yes":
                raise ValueError("Debes confirmar el perfilado y dry-run individual.")
            parsed_submission_id = _uuid(submission_id, "submission_id")
            result = await run_in_threadpool(
                gateway.promote_intake,
                parsed_submission_id,
                resolved_intake_root,
                resolved_promotion_output,
                session.actor,
                reason,
                DEFAULT_MAX_PILOT_ROWS,
            )
        except (ValueError, RuntimeError, PermissionError, NotImplementedError) as exc:
            return _error(environment, 409, "Promoción no aplicada", str(exc), session=session)
        except Exception as exc:
            diagnostic_id = secrets.token_hex(4)
            LOGGER.error(
                "promotion_failed diagnostic_id=%s submission_id=%s error_type=%s sqlstate=%s",
                diagnostic_id, submission_id, type(exc).__name__, getattr(exc, "sqlstate", None),
            )
            return _error(
                environment, 503, "Promoción no disponible",
                f"No se creó el dry-run. Diagnóstico {diagnostic_id}; revisa esa referencia en la consola.",
                session=session,
            )
        return RedirectResponse(
            f"/operator/intake?{urlencode({'result': str(result['status'])})}",
            status_code=303,
        )

    @app.post("/operator/intake/{submission_id}/index-images")
    async def index_image_archive_route(request: Request, submission_id: str) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        session = session_or_redirect
        try:
            form = await _parse_form(request)
            if set(form) != {"csrf_token", "reason", "confirm"}:
                raise ValueError("El formulario contiene campos ausentes o desconocidos.")
            if not _same_origin(request) or not hmac.compare_digest(form["csrf_token"], session.csrf_token):
                return _error(environment, 403, "Solicitud rechazada", "La evidencia CSRF no coincide.", session=session)
            reason = _require_text(form["reason"], "reason")
            if not 4 <= len(reason) <= MAX_REASON_LENGTH:
                raise ValueError("reason debe contener entre 4 y 500 caracteres.")
            if form["confirm"] != "yes":
                raise ValueError("Debes confirmar la indexación individual sin extracción.")
            result = await run_in_threadpool(
                gateway.index_image_archive,
                _uuid(submission_id, "submission_id"), resolved_intake_root, session.actor, reason,
            )
        except (ValueError, RuntimeError, PermissionError, NotImplementedError) as exc:
            return _error(environment, 409, "Índice no creado", str(exc), session=session)
        except Exception as exc:
            return _unexpected_error(environment, "Indexación no disponible", "No se creó el índice. Revisa la consola del servidor.", "image_index_failed", exc, session=session)
        return RedirectResponse(
            f"/operator/intake?{urlencode({'result': str(result['status'])})}", status_code=303
        )

    @app.get("/operator/images", response_class=HTMLResponse)
    async def image_candidates_page(request: Request, page: int = 1) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        try:
            if page < 1 or page > 100_000:
                raise ValueError("Página fuera del rango permitido.")
            limit = 50
            candidates = await run_in_threadpool(
                gateway.image_candidates, limit=limit, offset=(page - 1) * limit,
                company_id=session_or_redirect.company_id,
            )
        except ValueError as exc:
            return _error(environment, 400, "Página inválida", str(exc), session=session_or_redirect)
        except Exception as exc:
            return _unexpected_error(environment, "Revisión de imágenes no disponible", "Verifica que la actualización del sistema esté aplicada y revisa la consola del servidor.", "image_review_read_failed", exc, session=session_or_redirect)
        result_message = {
            "generated": "Candidatos exactos generados. Ninguno fue aprobado automáticamente.",
            "approved": "Candidato de imagen aprobado con su evidencia exacta.",
            "rejected": "Candidato de imagen rechazado; la evidencia permanece conservada.",
            "already_approved": "La aprobación exacta ya existía.",
            "already_rejected": "El rechazo exacto ya existía.",
            "bulk_approved": "Asociaciones pendientes aprobadas en lote; cada hash quedó registrado.",
            "bulk_rejected": "Asociaciones pendientes rechazadas en lote; la evidencia permanece intacta.",
            "materialized": "Imagen verificada y copiada al almacenamiento content-addressed.",
            "already_materialized": "La imagen aprobada ya estaba materializada.",
            "bulk_materialized": "Imágenes aprobadas materializadas en lote. Construye una versión nueva para incluirlas.",
            "exact_images_ready": "Coincidencias exactas aprobadas y materializadas. Ya puedes construir una versión nueva.",
        }.get(request.query_params.get("result"))
        previous_url = f"/operator/images?page={page - 1}" if page > 1 else None
        next_url = f"/operator/images?page={page + 1}" if page * limit < candidates["filtered_count"] else None
        return _render(
            environment, "operator_images.html", candidates=candidates,
            message=result_message, page=page, previous_url=previous_url, next_url=next_url,
            session=session_or_redirect, version=OPERATOR_VERSION,
        )

    @app.post("/operator/images/index/{index_id}/candidates")
    async def generate_image_candidates_route(request: Request, index_id: str) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        session = session_or_redirect
        try:
            form = await _parse_form(request)
            if set(form) != {"csrf_token", "reason", "confirm"}:
                raise ValueError("El formulario contiene campos ausentes o desconocidos.")
            if not _same_origin(request) or not hmac.compare_digest(form["csrf_token"], session.csrf_token):
                return _error(environment, 403, "Solicitud rechazada", "La evidencia CSRF no coincide.", session=session)
            reason = _require_text(form["reason"], "reason")
            if not 4 <= len(reason) <= MAX_REASON_LENGTH:
                raise ValueError("reason debe contener entre 4 y 500 caracteres.")
            if form["confirm"] != "yes":
                raise ValueError("Debes confirmar la generación exacta de candidatos.")
            await run_in_threadpool(
                gateway.generate_image_candidates, _uuid(index_id, "image_archive_index_id"),
                session.actor, reason, session.company_id,
            )
        except (ValueError, RuntimeError, PermissionError) as exc:
            return _error(environment, 409, "Candidatos no generados", str(exc), session=session)
        except Exception as exc:
            return _unexpected_error(environment, "Generación no disponible", "No se generaron candidatos. Revisa la consola.", "image_candidates_generate_failed", exc, session=session)
        return RedirectResponse("/operator/images?result=generated", status_code=303)

    @app.post("/operator/images/candidates/{candidate_id}/decision")
    async def decide_image_candidate_route(request: Request, candidate_id: str) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        session = session_or_redirect
        try:
            form = await _parse_form(request)
            if set(form) != {"csrf_token", "evidence_sha256", "decision", "reason", "confirm"}:
                raise ValueError("El formulario contiene campos ausentes o desconocidos.")
            if not _same_origin(request) or not hmac.compare_digest(form["csrf_token"], session.csrf_token):
                return _error(environment, 403, "Solicitud rechazada", "La evidencia CSRF no coincide.", session=session)
            reason = _require_text(form["reason"], "reason")
            if not 4 <= len(reason) <= MAX_REASON_LENGTH:
                raise ValueError("reason debe contener entre 4 y 500 caracteres.")
            if form["confirm"] != "yes":
                raise ValueError("Debes confirmar la decisión individual.")
            result = await run_in_threadpool(
                gateway.decide_image_candidate, _uuid(candidate_id, "candidate_id"),
                form["evidence_sha256"], form["decision"], session.actor, reason,
                session.company_id,
            )
        except (ValueError, RuntimeError, PermissionError) as exc:
            return _error(environment, 409, "Decisión no aplicada", str(exc), session=session)
        except Exception:
            diagnostic_id = uuid.uuid4().hex[:12]
            LOGGER.exception("Fallo al decidir candidato de imagen; diagnostico=%s", diagnostic_id)
            return _error(
                environment, 503, "Decisión no disponible",
                f"No se guardó la decisión. Diagnóstico: {diagnostic_id}.", session=session,
            )
        return RedirectResponse(
            f"/operator/images?{urlencode({'result': str(result['status'])})}", status_code=303
        )

    @app.post("/operator/images/candidates/bulk-decision")
    async def decide_image_candidates_bulk_route(request: Request) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        session = session_or_redirect
        try:
            form = await _parse_form(request)
            if set(form) != {"csrf_token", "expected_count", "decision", "reason", "confirm"}:
                raise ValueError("El formulario contiene campos ausentes o desconocidos.")
            if not _same_origin(request) or not hmac.compare_digest(form["csrf_token"], session.csrf_token):
                return _error(environment, 403, "Solicitud rechazada", "La evidencia CSRF no coincide.", session=session)
            reason = _require_text(form["reason"], "reason")
            if not 4 <= len(reason) <= MAX_REASON_LENGTH:
                raise ValueError("reason debe contener entre 4 y 500 caracteres.")
            decision = form["decision"]
            if decision not in {"approved", "rejected"} or form["confirm"] != decision:
                raise ValueError("La confirmación explícita no coincide con la decisión por lote.")
            expected_count = int(form["expected_count"])
            result = await run_in_threadpool(
                gateway.decide_image_candidates_bulk,
                expected_count, decision, session.actor, reason, session.company_id,
            )
        except (ValueError, RuntimeError, PermissionError) as exc:
            return _error(environment, 409, "Lote no aplicado", str(exc), session=session)
        except Exception:
            diagnostic_id = uuid.uuid4().hex[:12]
            LOGGER.exception("Fallo al decidir lote de imágenes; diagnostico=%s", diagnostic_id)
            return _error(
                environment, 503, "Decisión no disponible",
                f"No se guardó el lote. Diagnóstico: {diagnostic_id}.", session=session,
            )
        return RedirectResponse(
            f"/operator/images?{urlencode({'result': str(result['status'])})}", status_code=303
        )

    @app.post("/operator/images/candidates/prepare-exact")
    async def prepare_exact_images_route(request: Request) -> Response:
        """Una confirmación humana: aprueba las coincidencias exactas y copia sus archivos."""
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        session = session_or_redirect
        try:
            form = await _parse_form(request)
            required = {"csrf_token", "pending_count", "approved_count", "reason", "confirm"}
            if set(form) != required:
                raise ValueError("El formulario contiene campos ausentes o desconocidos.")
            if not _same_origin(request) or not hmac.compare_digest(form["csrf_token"], session.csrf_token):
                return _error(environment, 403, "Solicitud rechazada", "La evidencia CSRF no coincide.", session=session)
            if form["confirm"] != "yes":
                raise ValueError("Debes confirmar la preparación de las coincidencias exactas.")
            reason = _require_text(form["reason"], "reason")
            if not 4 <= len(reason) <= MAX_REASON_LENGTH:
                raise ValueError("reason debe contener entre 4 y 500 caracteres.")
            pending_count = int(form["pending_count"])
            approved_count = int(form["approved_count"])
            total = pending_count + approved_count
            if not 1 <= total <= 500:
                raise ValueError("El lote preparado debe contener entre 1 y 500 imágenes.")
            if pending_count:
                await run_in_threadpool(
                    gateway.decide_image_candidates_bulk,
                    pending_count, "approved", session.actor, reason, session.company_id,
                )
            await run_in_threadpool(
                gateway.materialize_approved_images_bulk, total,
                resolved_intake_root, resolved_image_output, session.actor, reason,
                session.company_id,
            )
        except (ValueError, RuntimeError, PermissionError, FileExistsError) as exc:
            return _error(environment, 409, "Preparación no completada", str(exc), session=session)
        except Exception:
            diagnostic_id = uuid.uuid4().hex[:12]
            LOGGER.exception("Fallo al preparar imágenes exactas; diagnostico=%s", diagnostic_id)
            return _error(environment, 503, "Preparación no disponible", f"No se completó el lote. Diagnóstico: {diagnostic_id}.", session=session)
        return RedirectResponse("/operator/images?result=exact_images_ready", status_code=303)

    @app.post("/operator/images/candidates/{candidate_id}/materialize")
    async def materialize_approved_image_route(request: Request, candidate_id: str) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        session = session_or_redirect
        try:
            form = await _parse_form(request)
            if set(form) != {"csrf_token", "evidence_sha256", "reason", "confirm"}:
                raise ValueError("El formulario contiene campos ausentes o desconocidos.")
            if not _same_origin(request) or not hmac.compare_digest(form["csrf_token"], session.csrf_token):
                return _error(environment, 403, "Solicitud rechazada", "La evidencia CSRF no coincide.", session=session)
            reason = _require_text(form["reason"], "reason")
            if not 4 <= len(reason) <= MAX_REASON_LENGTH:
                raise ValueError("reason debe contener entre 4 y 500 caracteres.")
            if form["confirm"] != "yes":
                raise ValueError("Debes confirmar la copia verificada de la imagen aprobada.")
            result = await run_in_threadpool(
                gateway.materialize_approved_image, _uuid(candidate_id, "candidate_id"),
                form["evidence_sha256"], resolved_intake_root, resolved_image_output,
                session.actor, reason, session.company_id,
            )
        except (ValueError, RuntimeError, PermissionError, FileExistsError) as exc:
            return _error(environment, 409, "Imagen no materializada", str(exc), session=session)
        except Exception as exc:
            return _unexpected_error(environment, "Materialización no disponible", "No se publicó la copia verificada. Revisa la consola.", "image_materialize_failed", exc, session=session)
        return RedirectResponse(
            f"/operator/images?{urlencode({'result': str(result['status'])})}", status_code=303
        )

    @app.post("/operator/images/candidates/bulk-materialize")
    async def materialize_approved_images_bulk_route(request: Request) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        session = session_or_redirect
        try:
            form = await _parse_form(request)
            if set(form) != {"csrf_token", "expected_count", "reason", "confirm"}:
                raise ValueError("El formulario contiene campos ausentes o desconocidos.")
            if not _same_origin(request) or not hmac.compare_digest(form["csrf_token"], session.csrf_token):
                return _error(environment, 403, "Solicitud rechazada", "La evidencia CSRF no coincide.", session=session)
            if form["confirm"] != "yes":
                raise ValueError("Debes confirmar la materialización del lote exacto.")
            reason = _require_text(form["reason"], "reason")
            if not 4 <= len(reason) <= MAX_REASON_LENGTH:
                raise ValueError("reason debe contener entre 4 y 500 caracteres.")
            result = await run_in_threadpool(
                gateway.materialize_approved_images_bulk, int(form["expected_count"]),
                resolved_intake_root, resolved_image_output, session.actor, reason,
                session.company_id,
            )
        except (ValueError, RuntimeError, PermissionError, FileExistsError) as exc:
            return _error(environment, 409, "Lote no materializado", str(exc), session=session)
        except Exception:
            diagnostic_id = uuid.uuid4().hex[:12]
            LOGGER.exception("Fallo al materializar lote de imágenes; diagnostico=%s", diagnostic_id)
            return _error(environment, 503, "Materialización no disponible", f"No se materializó el lote. Diagnóstico: {diagnostic_id}.", session=session)
        return RedirectResponse(f"/operator/images?{urlencode({'result': str(result['status'])})}", status_code=303)

    @app.get("/operator/plans/{plan_id}", response_class=HTMLResponse)
    async def review_queue(
        request: Request,
        plan_id: str,
        q: str = "",
        state: str = "pending",
        page: int = 1,
    ) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        try:
            parsed_plan_id = _uuid(plan_id, "plan_id")
            if state not in REVIEW_STATES:
                raise ValueError("Filtro de estado inválido.")
            if page < 1 or page > 100_000:
                raise ValueError("Página fuera del rango permitido.")
            if len(q) > 200:
                raise ValueError("La búsqueda no puede superar 200 caracteres.")
            plan = await run_in_threadpool(gateway.plan, parsed_plan_id)
            if plan is None:
                return _error(environment, 404, "Plan no encontrado", "No existe un plan aplicado revisable con ese UUID.", session=session_or_redirect)
            limit = 50
            queue = await run_in_threadpool(
                gateway.page,
                parsed_plan_id,
                plan["approval_fingerprint_sha256"],
                query=q,
                state=state,
                limit=limit,
                offset=(page - 1) * limit,
            )
        except (ValueError, RuntimeError, PermissionError) as exc:
            return _error(environment, 400, "No se pudo abrir la cola", str(exc), session=session_or_redirect)
        except Exception as exc:
            return _unexpected_error(environment, "PostgreSQL no disponible", "No se pudo leer la cola. Revisa la consola del servidor operador.", "review_queue_read_failed", exc, session=session_or_redirect)
        query_args = {"q": q, "state": state}
        previous_url = (
            f"/operator/plans/{plan_id}?{urlencode({**query_args, 'page': page - 1})}"
            if page > 1
            else None
        )
        next_url = (
            f"/operator/plans/{plan_id}?{urlencode({**query_args, 'page': page + 1})}"
            if page * limit < queue["filtered_count"]
            else None
        )
        result = request.query_params.get("result")
        message = {
            "approved": "Producto aprobado y auditado.",
            "rejected": "Producto rechazado y conservado para corrección.",
            "already_approved": "La aprobación ya existía con la misma evidencia.",
            "already_rejected": "El rechazo ya existía con la misma evidencia.",
            "bulk_approved": "Lote pendiente aprobado y auditado identidad por identidad.",
            "bulk_rejected": "Lote pendiente rechazado y auditado identidad por identidad.",
        }.get(result)
        return _render(
            environment,
            "operator_queue.html",
            plan=plan,
            queue=queue,
            q=q,
            selected_state=state,
            states=("pending", "approved", "rejected", "inconsistent", "all"),
            page=page,
            previous_url=previous_url,
            next_url=next_url,
            message=message,
            session=session_or_redirect,
            version=OPERATOR_VERSION,
        )

    @app.get("/operator/import-plans/{plan_id}", response_class=HTMLResponse)
    async def inspect_import_plan_route(request: Request, plan_id: str) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        try:
            plan = await run_in_threadpool(gateway.import_plan, _uuid(plan_id, "plan_id"))
            profiles = await run_in_threadpool(
                gateway.brand_profiles, company_id=session_or_redirect.company_id,
            )
        except ValueError as exc:
            return _error(environment, 404, "Plan no encontrado", str(exc), session=session_or_redirect)
        except Exception:
            diagnostic_id = uuid.uuid4().hex[:12]
            LOGGER.exception("Fallo al inspeccionar plan; diagnostico=%s", diagnostic_id)
            return _error(
                environment, 503, "No se pudo consultar el plan",
                f"La consulta falló; PostgreSQL puede seguir activo. Diagnóstico: {diagnostic_id}.",
                session=session_or_redirect,
            )
        result = request.query_params.get("result")
        message = {
            "approved": "Plan aprobado. Aún no se han creado productos.",
            "applied": "Plan aplicado. Sus productos ya están pendientes de revisión individual.",
            "prepared": "Importación verificada y preparada. Revisa sólo las identidades y aplicaciones detectadas.",
            "already_applied": "El plan ya estaba aplicado.",
        }.get(result)
        return _render(
            environment, "operator_import_plan.html", plan=plan, profiles=profiles, message=message,
            session=session_or_redirect, version=OPERATOR_VERSION,
        )

    async def _import_plan_transition(
        request: Request, plan_id: str, transition: str,
    ) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        session = session_or_redirect
        try:
            form = await _parse_form(request)
            expected_fields = {"csrf_token", "fingerprint", "reason", "confirm"}
            if transition == "prepare":
                expected_fields.add("brand_code")
            if set(form) != expected_fields:
                raise ValueError("El formulario contiene campos ausentes o desconocidos.")
            if not _same_origin(request) or not hmac.compare_digest(form["csrf_token"], session.csrf_token):
                return _error(environment, 403, "Solicitud rechazada", "La evidencia CSRF no coincide.", session=session)
            reason = _require_text(form["reason"], "reason")
            if not 4 <= len(reason) <= MAX_REASON_LENGTH:
                raise ValueError("reason debe contener entre 4 y 500 caracteres.")
            if form["confirm"] != transition:
                raise ValueError("La confirmación explícita no coincide con la operación.")
            parsed_plan_id = _uuid(plan_id, "plan_id")
            action = (
                gateway.prepare_import_plan if transition == "prepare"
                else gateway.approve_import_plan if transition == "approve"
                else gateway.apply_import_plan
            )
            args = [parsed_plan_id, form["fingerprint"], session.actor, reason]
            if transition == "prepare":
                args.append(_require_text(form["brand_code"], "brand_code"))
            result = await run_in_threadpool(action, *args)
        except (ValueError, RuntimeError, PermissionError, NotImplementedError) as exc:
            return _error(environment, 409, "Operación no aplicada", str(exc), session=session)
        except Exception as exc:
            return _unexpected_error(environment, "Operación no disponible", "No se modificó el plan. Revisa la consola.", "import_plan_transition_failed", exc, session=session)
        return RedirectResponse(
            f"/operator/import-plans/{plan_id}?{urlencode({'result': str(result['status'])})}",
            status_code=303,
        )

    @app.post("/operator/import-plans/{plan_id}/approve")
    async def approve_import_plan_route(request: Request, plan_id: str) -> Response:
        return await _import_plan_transition(request, plan_id, "approve")

    @app.post("/operator/import-plans/{plan_id}/apply")
    async def apply_import_plan_route(request: Request, plan_id: str) -> Response:
        return await _import_plan_transition(request, plan_id, "apply")

    @app.post("/operator/import-plans/{plan_id}/prepare")
    async def prepare_import_plan_route(request: Request, plan_id: str) -> Response:
        return await _import_plan_transition(request, plan_id, "prepare")

    @app.post("/operator/plans/{plan_id}/products/{product_id}/decision")
    async def decide(request: Request, plan_id: str, product_id: str) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        session = session_or_redirect
        try:
            form = await _parse_form(request)
            if not _same_origin(request) or not hmac.compare_digest(
                form.get("csrf_token", ""), session.csrf_token
            ):
                return _error(environment, 403, "Solicitud rechazada", "La evidencia CSRF no coincide.", session=session)
            reason = _require_text(form.get("reason", ""), "reason")
            if len(reason) < 4:
                raise ValueError("reason debe contener al menos 4 caracteres.")
            if len(reason) > MAX_REASON_LENGTH:
                raise ValueError(f"reason no puede superar {MAX_REASON_LENGTH} caracteres.")
            if form.get("confirm") != "yes":
                raise ValueError("Debes confirmar explícitamente la decisión individual.")
            parsed_plan_id = _uuid(plan_id, "plan_id")
            parsed_product_id = _uuid(product_id, "product_id")
            result = await run_in_threadpool(
                gateway.decide,
                parsed_plan_id,
                parsed_product_id,
                form.get("fingerprint", ""),
                form.get("review_sha256", ""),
                form.get("decision", ""),
                session.actor,
                reason,
            )
        except (ValueError, RuntimeError, PermissionError, NotImplementedError) as exc:
            return _error(environment, 409, "Decisión no aplicada", str(exc), session=session)
        except Exception as exc:
            return _unexpected_error(environment, "PostgreSQL no disponible", "La decisión no se escribió. Revisa la consola del servidor operador.", "product_decision_failed", exc, session=session)
        result_code = str(result["status"])
        return RedirectResponse(
            f"/operator/plans/{plan_id}?{urlencode({'state': 'pending', 'result': result_code})}",
            status_code=303,
        )

    @app.post("/operator/plans/{plan_id}/bulk-decision")
    async def decide_bulk(request: Request, plan_id: str) -> Response:
        session_or_redirect = require_session(request)
        if isinstance(session_or_redirect, RedirectResponse):
            return session_or_redirect
        session = session_or_redirect
        try:
            form = await _parse_form(request)
            if set(form) != {"csrf_token", "fingerprint", "query", "expected_count", "decision", "reason", "confirm"}:
                raise ValueError("El formulario contiene campos ausentes o desconocidos.")
            if not _same_origin(request) or not hmac.compare_digest(form["csrf_token"], session.csrf_token):
                return _error(environment, 403, "Solicitud rechazada", "La evidencia CSRF no coincide.", session=session)
            decision = form["decision"]
            if decision not in {"approve", "reject"} or form["confirm"] != decision:
                raise ValueError("Debes confirmar exactamente la decisión del lote.")
            reason = _require_text(form["reason"], "reason")
            if not 4 <= len(reason) <= MAX_REASON_LENGTH:
                raise ValueError("reason debe contener entre 4 y 500 caracteres.")
            query = form["query"].strip()
            if len(query) > 200:
                raise ValueError("La búsqueda no puede superar 200 caracteres.")
            expected_count = int(form["expected_count"])
            result = await run_in_threadpool(
                gateway.decide_many, _uuid(plan_id, "plan_id"), form["fingerprint"],
                decision, session.actor, reason, query=query, expected_count=expected_count,
            )
        except (ValueError, RuntimeError, PermissionError, NotImplementedError) as exc:
            return _error(environment, 409, "Lote no aplicado", str(exc), session=session)
        except Exception as exc:
            return _unexpected_error(environment, "PostgreSQL no disponible", "Ninguna decisión del lote fue escrita. Revisa la consola.", "product_bulk_decision_failed", exc, session=session)
        return RedirectResponse(
            f"/operator/plans/{plan_id}?{urlencode({'state': 'pending', 'result': str(result['status'])})}",
            status_code=303,
        )

    return app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inicia la consola local protegida de revisión humana."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--database", default=None)
    parser.add_argument("--user", default=None)
    parser.add_argument("--db-host", dest="host_db", default=None)
    parser.add_argument("--db-port", dest="port_db", type=int, default=None)
    parser.add_argument("--intake-dir", default="data/intake")
    parser.add_argument("--promotion-output-dir", default="data/exports/imports")
    parser.add_argument("--catalog-output-dir", default="data/exports/catalogs")
    parser.add_argument("--image-output-dir", default="data/images")
    parser.add_argument("--prompt-password", action="store_true")
    parser.add_argument("--prompt-operator", action="store_true")
    parser.add_argument("--prompt-access-code", action="store_true")
    parser.add_argument("--operator", default=None)
    parser.add_argument("--generate-access-code", action="store_true")
    parser.add_argument("--open-browser", action="store_true")
    return parser


def _prompt_actor(enabled: bool) -> str:
    if not enabled:
        raise ValueError("Se requiere --prompt-operator; el actor no se acepta en argumentos.")
    return _require_text(input("Nombre del operador que quedará en auditoría: "), "actor")


def _operator_actor(args: argparse.Namespace) -> str:
    if args.prompt_operator and args.operator:
        raise ValueError("Usa --prompt-operator o --operator, no ambos.")
    actor = _prompt_actor(True) if args.prompt_operator else (args.operator or getpass.getuser())
    return _require_text(actor, "actor")


def _prompt_access_code(enabled: bool) -> str:
    if not enabled:
        raise ValueError("Se requiere --prompt-access-code; el código no se acepta en argumentos.")
    first = getpass.getpass("Código temporal para entrar a la web (mínimo 12 caracteres): ")
    second = getpass.getpass("Confirma el código temporal: ")
    if not hmac.compare_digest(first, second):
        raise ValueError("Los códigos temporales no coinciden.")
    return first


def _operator_access_code(args: argparse.Namespace) -> tuple[str, bool]:
    if args.prompt_access_code and args.generate_access_code:
        raise ValueError("Usa --prompt-access-code o --generate-access-code, no ambos.")
    if args.prompt_access_code:
        return _prompt_access_code(True), False
    if args.generate_access_code:
        return "-".join(secrets.token_hex(3).upper() for _ in range(3)), True
    raise ValueError("Se requiere --prompt-access-code o --generate-access-code.")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    gateway: DatabaseReviewGateway | None = None
    try:
        if args.host not in {"127.0.0.1", "localhost"}:
            raise ValueError("El modo operador solo puede escuchar en localhost.")
        database_args = argparse.Namespace(
            host=args.host_db,
            port=args.port_db,
            database=args.database,
            user=args.user,
        )
        config = DatabaseConfig.from_args(database_args)
        database_password = prompt_password(args.prompt_password)
        gateway = DatabaseReviewGateway(config, database_password)
        gateway.plans(limit=1)
        gateway.intake_submissions(limit=1)
        actor = _operator_actor(args)
        access_code, generated_access = _operator_access_code(args)
        authenticator = OperatorAuthenticator(actor, access_code)
        database_password = ""
    except (ValueError, EOFError, KeyboardInterrupt, psycopg.Error) as exc:
        if gateway is not None:
            gateway.close()
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Consola de revisión: http://{args.host}:{args.port}/operator")
    print(f"Operador de auditoría: {actor}")
    if generated_access:
        print(f"Código temporal web generado: {access_code}")
    access_code = ""
    print("Acceso temporal, solo local. Presiona Ctrl+C para detener.")
    if args.open_browser:
        threading.Timer(
            1.0, lambda: webbrowser.open(f"http://{args.host}:{args.port}/operator/login")
        ).start()
    uvicorn.run(
        create_operator_app(
            gateway,
            authenticator,
            intake_root=Path(args.intake_dir),
            promotion_output_dir=Path(args.promotion_output_dir),
            catalog_output_dir=Path(args.catalog_output_dir),
            image_output_dir=Path(args.image_output_dir),
        ),
        host=args.host,
        port=args.port,
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
