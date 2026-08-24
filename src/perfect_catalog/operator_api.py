from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import hmac
import secrets
import sys
import threading
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.parse import parse_qs, urlencode, urlsplit

import uvicorn
import psycopg
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import DatabaseConfig, prompt_password
from .intake import (
    INTAKE_KINDS,
    MAX_UPLOAD_REQUEST_BYTES,
    SecureIntakeService,
    intake_kind_options,
)
from .reviews import DatabaseReviewGateway, REVIEW_STATES, _require_text


OPERATOR_VERSION = "1.1.0"
SESSION_COOKIE = "pc_operator_session"
LOGIN_COOKIE = "pc_operator_login"
MAX_FORM_BYTES = 16_384
MAX_REASON_LENGTH = 500
SESSION_TTL_SECONDS = 60 * 60
LOGIN_CHALLENGE_TTL_SECONDS = 10 * 60
PBKDF2_ITERATIONS = 310_000


class ReviewGateway(Protocol):
    def close(self) -> None: ...

    def plans(self, *, limit: int = 100) -> list[dict[str, Any]]: ...

    def plan(self, plan_id: uuid.UUID) -> dict[str, Any] | None: ...

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

    def intake_submissions(
        self,
        *,
        kind: str = "all",
        status: str = "all",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]: ...

    def record_intake(self, record: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class OperatorSession:
    session_id: str
    actor: str
    csrf_token: str
    expires_at: int


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

    def authenticate(self, access_code: str) -> bool:
        now = self._now()
        with self._lock:
            self._failed_logins = [
                attempt for attempt in self._failed_logins if now - attempt < 300
            ]
            if len(self._failed_logins) >= 5:
                return False
        valid = hmac.compare_digest(self._derive(access_code), self._access_digest)
        with self._lock:
            if valid:
                self._failed_logins.clear()
            else:
                self._failed_logins.append(now)
        return valid

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
        "default-src 'none'; style-src 'self'; img-src 'self'; "
        "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
    )
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"


def _same_origin(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return False
    try:
        parsed = urlsplit(origin)
        request_port = request.url.port or (
            443 if request.url.scheme == "https" else 80
        )
        origin_port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return False
    return (
        parsed.scheme == request.url.scheme
        and parsed.hostname == request.url.hostname
        and origin_port == request_port
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
        max_num_fields=20,
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


def create_operator_app(
    gateway: ReviewGateway,
    authenticator: OperatorAuthenticator,
    *,
    intake_root: Path | None = None,
) -> FastAPI:
    environment = _templates()
    intake_service = SecureIntakeService(
        intake_root or Path("data/intake"), gateway
    )

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
        response = await call_next(request)
        _set_security_headers(response)
        return response

    def current_session(request: Request) -> OperatorSession | None:
        return authenticator.get_session(request.cookies.get(SESSION_COOKIE))

    def require_session(request: Request) -> OperatorSession | RedirectResponse:
        session = current_session(request)
        if session is None:
            return RedirectResponse("/operator/login", status_code=303)
        return session

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
            path="/operator/login",
        )
        return response

    @app.post("/operator/login", response_class=HTMLResponse)
    async def login(request: Request) -> Response:
        try:
            form = await _parse_form(request)
        except (ValueError, UnicodeDecodeError) as exc:
            return _error(environment, 400, "Formulario inválido", str(exc))
        valid_origin = _same_origin(request)
        valid_challenge = authenticator.validate_login_challenge(
            request.cookies.get(LOGIN_COOKIE), form.get("csrf_token", "")
        )
        valid_code = False
        if valid_origin and valid_challenge:
            valid_code = await run_in_threadpool(
                authenticator.authenticate, form.get("access_code", "")
            )
        if not (valid_origin and valid_challenge and valid_code):
            challenge, signed_challenge = authenticator.issue_login_challenge()
            response = _render(
                environment,
                "operator_login.html",
                login_csrf=challenge,
                error="Acceso rechazado. Verifica el código y vuelve a intentarlo.",
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
                path="/operator/login",
            )
            return response
        _, signed_session = authenticator.create_session()
        response = RedirectResponse("/operator", status_code=303)
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
            plans = await run_in_threadpool(gateway.plans, limit=100)
        except Exception:
            return _error(
                environment,
                503,
                "PostgreSQL no disponible",
                "No se pudo leer la cola. Revisa la consola del servidor operador.",
                session=session_or_redirect,
            )
        return _render(
            environment,
            "operator_plans.html",
            plans=plans,
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
            )
        except ValueError as exc:
            return _error(
                environment,
                400,
                "Filtro inválido",
                str(exc),
                session=session_or_redirect,
            )
        except Exception:
            return _error(
                environment,
                503,
                "PostgreSQL no disponible",
                "No se pudo leer el historial de ingresos. "
                "Revisa la consola del servidor operador.",
                session=session_or_redirect,
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
        except Exception:
            return _error(
                environment,
                503,
                "Ingreso no disponible",
                "El archivo no quedó registrado. "
                "Revisa la consola del servidor operador.",
                session=session,
            )
        result = str(submitted["validation_status"])
        if submitted.get("duplicate_content"):
            result = "duplicate"
        return RedirectResponse(
            f"/operator/intake?{urlencode({'result': result})}", status_code=303
        )

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
        except Exception:
            return _error(environment, 503, "PostgreSQL no disponible", "No se pudo leer la cola. Revisa la consola del servidor operador.", session=session_or_redirect)
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
        except Exception:
            return _error(environment, 503, "PostgreSQL no disponible", "La decisión no se escribió. Revisa la consola del servidor operador.", session=session)
        result_code = str(result["status"])
        return RedirectResponse(
            f"/operator/plans/{plan_id}?{urlencode({'state': 'pending', 'result': result_code})}",
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
    parser.add_argument("--prompt-password", action="store_true")
    parser.add_argument("--prompt-operator", action="store_true")
    parser.add_argument("--prompt-access-code", action="store_true")
    return parser


def _prompt_actor(enabled: bool) -> str:
    if not enabled:
        raise ValueError("Se requiere --prompt-operator; el actor no se acepta en argumentos.")
    return _require_text(input("Nombre del operador que quedará en auditoría: "), "actor")


def _prompt_access_code(enabled: bool) -> str:
    if not enabled:
        raise ValueError("Se requiere --prompt-access-code; el código no se acepta en argumentos.")
    first = getpass.getpass("Código temporal para entrar a la web (mínimo 12 caracteres): ")
    second = getpass.getpass("Confirma el código temporal: ")
    if not hmac.compare_digest(first, second):
        raise ValueError("Los códigos temporales no coinciden.")
    return first


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
        actor = _prompt_actor(args.prompt_operator)
        access_code = _prompt_access_code(args.prompt_access_code)
        authenticator = OperatorAuthenticator(actor, access_code)
        database_password = ""
        access_code = ""
    except (ValueError, EOFError, KeyboardInterrupt, psycopg.Error) as exc:
        if gateway is not None:
            gateway.close()
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Consola de revisión: http://{args.host}:{args.port}/operator")
    print("Acceso temporal, solo local. Presiona Ctrl+C para detener.")
    uvicorn.run(
        create_operator_app(
            gateway, authenticator, intake_root=Path(args.intake_dir)
        ),
        host=args.host,
        port=args.port,
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
