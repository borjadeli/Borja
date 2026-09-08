"""Auth admin con cookie firmada — single-user (doc checkpoint).

Modelo simple:
- Password hash en ADMIN_PASSWORD_HASH del .env (generado con `generate_hash()`).
- Login en /login → valida password, setea cookie firmada con itsdangerous.
- Middleware protege rutas UI excepto /login, /logout, /static, /health (y /api salvo API_REQUIRE_AUTH).
- /api/* exento por defecto (curl/scripts locales); con API_REQUIRE_AUTH=1 también exige cookie (usar si es público).

Si ADMIN_PASSWORD_HASH está vacío en .env → auth deshabilitado (modo dev single-user local).
"""
from __future__ import annotations

import secrets
from typing import Callable

import bcrypt
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from itsdangerous import BadSignature, TimestampSigner
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from backend.config import get_settings
from backend.utils import get_logger

log = get_logger(__name__)

COOKIE_NAME = "borja_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 días

_PATHS_SIN_AUTH = (
    "/login", "/logout", "/static/", "/health",
)


# ---------- Hash helpers ----------

def generate_hash(password: str) -> str:
    """Genera un hash bcrypt. Uso: python -c 'from backend.auth import generate_hash; print(generate_hash(\"mi-clave\"))'"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ---------- Signer ----------

_signer: TimestampSigner | None = None


def _get_signer() -> TimestampSigner:
    global _signer
    if _signer is None:
        s = get_settings()
        # usa el password hash como secret si no hay otro — se regenera si se cambia
        secret = (s.admin_password_hash or secrets.token_hex(16))
        _signer = TimestampSigner(secret, salt="borja-session")
    return _signer


def sign_cookie(user: str) -> str:
    return _get_signer().sign(user.encode("utf-8")).decode("utf-8")


def verify_cookie(cookie_value: str, max_age: int = COOKIE_MAX_AGE) -> str | None:
    try:
        raw = _get_signer().unsign(cookie_value.encode("utf-8"), max_age=max_age)
        return raw.decode("utf-8")
    except (BadSignature, Exception):
        return None


# ---------- Auth enabled check ----------

def auth_enabled() -> bool:
    return bool(get_settings().admin_password_hash)


# ---------- Middleware ----------

class AuthMiddleware(BaseHTTPMiddleware):
    """Protege rutas UI con cookie firmada. Deja /api/* y /static abiertos."""

    async def dispatch(self, request: Request, call_next: Callable):
        if not auth_enabled():
            return await call_next(request)

        path = request.url.path
        exempt = _PATHS_SIN_AUTH if get_settings().api_require_auth else _PATHS_SIN_AUTH + ("/api/",)
        if any(path.startswith(p) for p in exempt):
            return await call_next(request)

        cookie = request.cookies.get(COOKIE_NAME)
        if cookie and verify_cookie(cookie):
            return await call_next(request)

        # Redirigir a /login
        return RedirectResponse(f"/login?next={path}", status_code=303)


# ---------- Login/Logout handlers (se registran en ui.py) ----------

LOGIN_TEMPLATE = """<!doctype html><html lang='es'><head><meta charset='utf-8'>
<title>Login · BORJA</title>
<script src='https://cdn.tailwindcss.com'></script>
<link href='https://fonts.googleapis.com/css2?family=IBM+Plex+Serif:wght@600;700&family=Inter:wght@400;600&display=swap' rel='stylesheet'>
</head><body class='bg-slate-100 min-h-screen flex items-center justify-center font-[Inter]'>
<form method='post' action='/login' class='bg-white border border-slate-200 rounded-lg shadow-sm p-8 w-96'>
  <h1 class='font-[IBM_Plex_Serif] text-3xl font-bold text-slate-900 mb-1'>BORJA</h1>
  <div class='text-xs uppercase tracking-widest text-slate-500 mb-6'>Investment System</div>
  {error}
  <input type='hidden' name='next' value='{next}'>
  <label class='text-xs uppercase tracking-widest text-slate-500 font-semibold'>Password</label>
  <input type='password' name='password' autofocus class='mt-1 mb-4 w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-indigo-500'>
  <button type='submit' class='w-full bg-slate-900 text-white px-4 py-2 rounded text-sm font-semibold hover:bg-slate-800'>Entrar</button>
</form></body></html>"""


def login_page(next_path: str = "/", error: str | None = None) -> HTMLResponse:
    error_html = f"<div class='mb-4 text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded px-3 py-2'>{error}</div>" if error else ""
    html = LOGIN_TEMPLATE.replace("{error}", error_html).replace("{next}", next_path)
    return HTMLResponse(html)


def do_login(password: str, next_path: str = "/") -> tuple[bool, RedirectResponse | HTMLResponse]:
    s = get_settings()
    if not auth_enabled():
        return True, RedirectResponse(next_path, status_code=303)

    if not verify_password(password, s.admin_password_hash):
        log.warning("login fallido — password incorrecta")
        return False, login_page(next_path, error="Password incorrecta")

    cookie_val = sign_cookie(s.admin_user)
    resp = RedirectResponse(next_path, status_code=303)
    resp.set_cookie(
        COOKIE_NAME, cookie_val,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=get_settings().cookie_secure,  # True en prod con HTTPS (COOKIE_SECURE=1)
    )
    log.info("login ok — user=%s", s.admin_user)
    return True, resp


def do_logout() -> RedirectResponse:
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp
