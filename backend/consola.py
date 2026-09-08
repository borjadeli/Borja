"""Consola Claude Code embebida (sidebar → /consola).

Mecanismo (portado de Purple SHIELD `dashboard/claude_chat.py`, adaptado a FastAPI):
  - `pty.fork()` lanza un hijo que corre `claude`; el padre conserva el master fd.
  - Un WebSocket (`/ws/consola/terminal`) puentea bytes fd↔ws en async.
  - El front (consola.html) es xterm.js — misma experiencia que la CLI real.

Sesión PERSISTENTE por usuario: el proceso `claude` + PTY se mantiene vivo en un pool
(`_SESSIONS`) aunque se cierre/recargue el WebSocket (F5). Un reader (`loop.add_reader`)
drena el PTY a un buffer de scrollback SIEMPRE (haya ws o no); al reconectar se reenvía
el buffer para que xterm rehidrate el estado visible. Idle timeout tras inactividad.

Sin dependencias nuevas: `pty`/`termios` son stdlib, FastAPI trae WebSocket nativo, y
xterm.js se carga por CDN. Se hace scrub de ANTHROPIC_API_KEY → `claude` usa la sesión
OAuth de `~/.claude.json` del usuario del host.

Auth: el AuthMiddleware (BaseHTTPMiddleware) NO intercepta WebSockets → la ruta WS se
autentica sola con la cookie de BORJA + check de Origin (anti-CSWSH). GET /consola sí
queda protegida por el middleware.
"""
from __future__ import annotations

import asyncio
import fcntl
import json
import os
import pty
import shutil
import signal
import struct
import termios
import time
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from backend.ui import _common_context, templates

router = APIRouter()

_SECRET_ENV_KEYS = {"ANTHROPIC_API_KEY", "ANTHROPIC_ADMIN_API_KEY",
                    "ADMIN_PASSWORD_HASH", "SMTP_PASSWORD"}
_SCROLLBACK = int(os.environ.get("CONSOLA_SCROLLBACK", "262144"))   # 256 KiB


def consola_enabled() -> bool:
    return os.environ.get("CONSOLA_ENABLED", "1").lower() in ("1", "true", "yes", "on")


def _idle_seconds() -> int:
    return int(os.environ.get("CONSOLA_IDLE_SECONDS", "14400"))       # 4 h


def _claude_bin() -> str:
    return (os.environ.get("CLAUDE_BIN")
            or shutil.which("claude")
            or os.path.expanduser("~/.local/bin/claude"))


def _default_cwd() -> str:
    return os.environ.get("CONSOLA_CWD") or str(Path(__file__).resolve().parent.parent)


def _build_child_env() -> dict:
    env = {k: v for k, v in os.environ.items() if k not in _SECRET_ENV_KEYS}
    env.setdefault("TERM", "xterm-256color")
    env.setdefault("LANG", env.get("LANG") or "en_US.UTF-8")
    env.setdefault("FORCE_COLOR", "1")
    return env


# ── Jail de filesystem (bubblewrap) ──────────────────────────────────
# La jaula confina el `claude` de la consola a un mount namespace donde SÓLO se ve
# CONSOLA_JAIL_ROOT (= el proyecto BORJA, read-write) + los dirs de sistema mínimos
# read-only que node/claude necesitan para ejecutarse (/usr,/etc,...) + el login de
# claude (~/.claude*). NADA más del filesystem (ni /home, ni el resto de /DATA, ni
# /var, ni claves) es visible. IMPORTANTE: esto es una barrera de SO real; la config
# de Claude Code NO lo es (la consola es un bash real). Requiere `bubblewrap` instalado
# y user-namespaces sin privilegios habilitados (default en Debian trixie/bookworm).
#
# FAIL-SAFE: la jaula está ACTIVA por defecto. Una variable ausente/vacía/con typo
# JAMÁS debe degradar a un shell con acceso total (fail-open). Sólo una desactivación
# EXPLÍCITA — CONSOLA_JAIL=0 — la apaga, y sólo debería hacerse en un entorno de
# confianza y no expuesto. Si la jaula está pedida pero bwrap no está disponible, la
# consola se REHÚSA a arrancar (fail-closed) en vez de exponer el filesystem.

def _jail_enabled() -> bool:
    """Fail-safe: ACTIVA salvo desactivación EXPLÍCITA (CONSOLA_JAIL=0/false/no/off).
    Ausente, vacío o cualquier otro valor → ACTIVA."""
    raw = os.environ.get("CONSOLA_JAIL")
    if raw is None or not raw.strip():
        return True
    return raw.strip().lower() not in ("0", "false", "no", "off")


def _bwrap_bin() -> str:
    return os.environ.get("BWRAP_BIN") or shutil.which("bwrap") or "/usr/bin/bwrap"


def _jail_root() -> str:
    return os.environ.get("CONSOLA_JAIL_ROOT") or _default_cwd()


def _home_dir() -> str:
    return os.environ.get("CONSOLA_HOME") or os.path.expanduser("~") or "/root"


def _jail_preflight() -> str | None:
    """None si la consola puede arrancar de forma segura; si no, un mensaje legible.
    NUNCA se cae a un shell sin jaula: si la jaula está pedida (default) pero bwrap no
    está disponible, se REHÚSA a arrancar (fail-closed)."""
    if not _jail_enabled():
        return None
    bwrap = _bwrap_bin()
    if not (bwrap and os.path.isfile(bwrap) and os.access(bwrap, os.X_OK)):
        return ("jaula de la consola ACTIVA pero no hay 'bwrap' ejecutable "
                f"({bwrap!r}). Instala bubblewrap (apt install bubblewrap) o, sólo en "
                "un entorno de confianza y NO expuesto, desactiva con CONSOLA_JAIL=0. "
                "Consola deshabilitada por seguridad.")
    return None


def _build_argv(claude_bin: str, cwd: str) -> list[str]:
    """argv para lanzar claude. Sin jail: [claude]. Con jail: [bwrap ... claude]."""
    if not _jail_enabled():
        return [claude_bin]

    root = _jail_root()
    home = _home_dir()
    argv = [
        _bwrap_bin(),
        # Runtime de sistema, read-only (node + libs). Merged-usr de Debian:
        "--ro-bind", "/usr", "/usr",
        "--symlink", "usr/bin", "/bin",
        "--symlink", "usr/sbin", "/sbin",
        "--symlink", "usr/lib", "/lib",
        "--symlink", "usr/lib64", "/lib64",
        "--ro-bind", "/etc", "/etc",             # TLS certs, resolv.conf, ...
        "--proc", "/proc",
        "--dev", "/dev",
        "--tmpfs", "/tmp",
        # El único árbol de DATOS visible, read-write:
        "--bind", root, root,
        # Login de claude (RW: refresca token). Únicos paths visibles fuera de root:
        "--bind-try", os.path.join(home, ".claude"), os.path.join(home, ".claude"),
        "--bind-try", os.path.join(home, ".claude.json"), os.path.join(home, ".claude.json"),
    ]
    # DNS: /etc/resolv.conf suele ser un symlink a /run/... (systemd-resolved). El --ro-bind
    # de /etc trae el symlink pero NO su destino (/run no se monta) → la jaula queda sin DNS
    # ("Could not resolve host"; claude no conecta a la API con ConnectionRefused). Montamos el
    # destino real del symlink para que /etc/resolv.conf resuelva dentro. En hosts con resolv.conf
    # como archivo real (p.ej. el notebook), realpath==/etc/resolv.conf → no se agrega nada.
    resolv_real = os.path.realpath("/etc/resolv.conf")
    if resolv_real and resolv_real != "/etc/resolv.conf":
        argv += ["--ro-bind-try", resolv_real, resolv_real]
    # El ejecutable `claude` casi siempre vive FUERA del root de la jaula (p.ej.
    # ~/.local/bin/claude → ~/.local/share/claude/versions/X, un binario nativo). Si no se
    # monta, bwrap aborta con `execvp <claude>: No such file or directory`. Se exponen
    # read-only SÓLO: el path invocado, el destino real del symlink, y —si cuelga del home—
    # su árbol de instalación (detección de versión/assets). No abre ninguna otra ruta.
    claude_real = os.path.realpath(claude_bin)
    ro_extra = [claude_bin, claude_real]
    inst_dir = os.path.dirname(claude_real)
    if inst_dir.startswith(os.path.realpath(home) + os.sep):
        ro_extra.append(inst_dir)
    seen_ro: set[str] = set()
    for p in ro_extra:
        if p and p != "/" and p not in seen_ro:
            seen_ro.add(p)
            argv += ["--ro-bind-try", p, p]
    for p in filter(None, (x.strip() for x in os.environ.get("CONSOLA_JAIL_RO", "").split(","))):
        argv += ["--ro-bind-try", p, p]
    for p in filter(None, (x.strip() for x in os.environ.get("CONSOLA_JAIL_RW", "").split(","))):
        argv += ["--bind-try", p, p]
    argv += [
        "--unshare-all", "--share-net",          # aísla todo menos la red (claude la usa)
        "--die-with-parent",
        "--chdir", root,
        claude_bin,
    ]
    return argv


def _set_winsize(fd: int, rows: int, cols: int) -> None:
    try:
        fcntl.ioctl(fd, termios.TIOCSWINSZ,
                    struct.pack("HHHH", max(1, rows), max(1, cols), 0, 0))
    except Exception:
        pass


def _origin_ok(websocket: WebSocket) -> bool:
    origin = websocket.headers.get("origin")
    if not origin:
        return True
    allowed = {websocket.headers.get("host", "")}
    for item in os.environ.get("CONSOLA_ALLOWED_ORIGINS", "").split(","):
        item = item.strip()
        if item:
            allowed.add(urlparse(item).netloc if "://" in item else item)
    return urlparse(origin).netloc in allowed


def _auth_user(websocket: WebSocket) -> str | None:
    """Devuelve el usuario de la cookie de BORJA, o None si no válida. Con auth
    deshabilitada, 'local'."""
    from backend.auth import COOKIE_NAME, auth_enabled, verify_cookie
    if not auth_enabled():
        return "local"
    cookie = websocket.cookies.get(COOKIE_NAME)
    return verify_cookie(cookie) if cookie else None


# ── Pool de sesiones PTY persistentes ────────────────────────────────
# Corre todo en el único event-loop de uvicorn (sin threads) → sin locks.

_SESSIONS: "dict[str, _ConsolaSession]" = {}
_reaper_started = False


class _ConsolaSession:
    def __init__(self, key: str, pid: int, fd: int, loop, idle_seconds: int):
        self.key = key
        self.pid = pid
        self.fd = fd
        self.loop = loop
        self.idle_seconds = idle_seconds
        self.buffer = bytearray()
        self.last_activity = time.time()
        self.active_ws = None
        self.active_queue: asyncio.Queue | None = None
        self.active_pump: asyncio.Task | None = None
        self.alive = True
        loop.add_reader(fd, self._on_readable)

    # PTY → buffer (siempre) + queue (si hay ws atado)
    def _on_readable(self) -> None:
        try:
            data = os.read(self.fd, 8192)
        except (BlockingIOError, InterruptedError):
            return
        except OSError:
            data = b""
        if not data:                       # EOF → claude terminó
            self._teardown()
            return
        self.buffer.extend(data)
        if len(self.buffer) > _SCROLLBACK:
            del self.buffer[: len(self.buffer) - _SCROLLBACK]
        self.last_activity = time.time()
        q = self.active_queue
        if q is not None:
            q.put_nowait(data)

    async def attach(self, ws) -> None:
        """Ata un ws nuevo: cancela el anterior, snapshotea el buffer (atómico, sin
        await entre snapshot y activación) y arranca el pump que reenvía replay + live."""
        if self.active_pump is not None:
            self.active_pump.cancel()
        old = self.active_ws
        q: asyncio.Queue = asyncio.Queue()
        replay = bytes(self.buffer)        # snapshot
        self.active_ws = ws                # desde acá, lo nuevo va a q
        self.active_queue = q
        self.last_activity = time.time()
        if old is not None and old is not ws:
            try:
                await old.send_text("\r\n\x1b[33m[sesión tomada por otra pestaña]\x1b[0m\r\n")
            except Exception:
                pass
            try:
                await old.close()
            except Exception:
                pass
        self.active_pump = self.loop.create_task(self._pump(ws, q, replay))

    async def _pump(self, ws, q: asyncio.Queue, replay: bytes) -> None:
        try:
            if replay:
                await ws.send_text(replay.decode("utf-8", "replace"))
            while True:
                data = await q.get()
                if data is None:           # sentinel de teardown
                    try:
                        await ws.send_text("\r\n\x1b[31m[claude session ended]\x1b[0m\r\n")
                        await ws.close()
                    except Exception:
                        pass
                    return
                await ws.send_text(data.decode("utf-8", "replace"))
        except asyncio.CancelledError:
            raise
        except Exception:
            pass

    def detach(self, ws) -> None:
        if self.active_ws is ws:
            self.active_ws = None
            self.active_queue = None
            if self.active_pump is not None:
                self.active_pump.cancel()
                self.active_pump = None

    def write(self, data: bytes) -> bool:
        try:
            os.write(self.fd, data)
            self.last_activity = time.time()
            return True
        except OSError:
            self._teardown()
            return False

    def resize(self, rows: int, cols: int) -> None:
        _set_winsize(self.fd, rows, cols)
        self.last_activity = time.time()

    def _teardown(self) -> None:
        if not self.alive:
            return
        self.alive = False
        try:
            self.loop.remove_reader(self.fd)
        except Exception:
            pass
        try:
            os.close(self.fd)
        except Exception:
            pass
        try:
            os.kill(self.pid, signal.SIGTERM)
        except Exception:
            pass
        try:
            os.waitpid(self.pid, os.WNOHANG)
        except Exception:
            pass
        if _SESSIONS.get(self.key) is self:
            del _SESSIONS[self.key]
        q = self.active_queue
        if q is not None:
            q.put_nowait(None)             # que el pump mande [ended] + cierre


def _spawn_session(key: str, loop) -> "_ConsolaSession":
    claude_bin = _claude_bin()
    cwd = _default_cwd()
    env = _build_child_env()
    argv = _build_argv(claude_bin, cwd)     # [claude] o [bwrap ... claude] si CONSOLA_JAIL=1
    pid, fd = pty.fork()
    if pid == 0:                            # ── hijo ──
        try:
            os.chdir(cwd)                   # bwrap re-hace --chdir; para el caso sin jail
        except Exception:
            pass
        try:
            os.execvpe(argv[0], argv, env)
        except Exception as e:  # noqa: BLE001
            os.write(2, f"failed to exec {argv[0]}: {e}\r\n".encode())
        os._exit(1)
    _set_winsize(fd, 28, 100)
    os.set_blocking(fd, False)
    return _ConsolaSession(key, pid, fd, loop, _idle_seconds())


def _get_or_create_session(key: str, loop) -> "_ConsolaSession":
    sess = _SESSIONS.get(key)
    if sess is not None and sess.alive:
        return sess
    sess = _spawn_session(key, loop)
    _SESSIONS[key] = sess
    return sess


def _ensure_reaper(loop) -> None:
    global _reaper_started
    if _reaper_started:
        return
    _reaper_started = True
    loop.create_task(_reaper())


async def _reaper() -> None:
    """Cierra sesiones inactivas más allá de idle_seconds."""
    while True:
        await asyncio.sleep(60)
        now = time.time()
        for sess in list(_SESSIONS.values()):
            if sess.alive and (now - sess.last_activity) > sess.idle_seconds:
                sess._teardown()


# ── Página ───────────────────────────────────────────────────────────

@router.get("/consola", response_class=HTMLResponse)
def consola_view(request: Request):
    ctx = _common_context(request, active="consola")
    ctx["consola_enabled"] = consola_enabled()
    return templates.TemplateResponse("consola.html", ctx)


@router.get("/api/consola/status")
def consola_status() -> dict:
    jail_err = _jail_preflight()
    return {"enabled": consola_enabled(), "claude_bin": _claude_bin(),
            "cwd": _default_cwd(), "sesiones_vivas": len(_SESSIONS),
            "jail": _jail_enabled(), "jail_root": _jail_root() if _jail_enabled() else None,
            "bwrap": _bwrap_bin() if _jail_enabled() else None,
            "jail_ready": jail_err is None, "jail_error": jail_err}


# ── WebSocket: PTY ↔ ws ───────────────────────────────────────────────

@router.websocket("/ws/consola/terminal")
async def consola_terminal(websocket: WebSocket):
    if not consola_enabled() or not _origin_ok(websocket):
        await websocket.close(code=1008)
        return
    user = _auth_user(websocket)
    if not user:
        await websocket.close(code=1008)
        return
    await websocket.accept()

    jail_err = _jail_preflight()
    if jail_err:
        try:
            await websocket.send_text(f"\r\n\x1b[31m[{jail_err}]\x1b[0m\r\n")
        except Exception:
            pass
        await websocket.close()
        return

    loop = asyncio.get_running_loop()
    _ensure_reaper(loop)
    key = f"user:{user}"
    try:
        sess = _get_or_create_session(key, loop)
    except Exception:
        try:
            await websocket.send_text("\r\n\x1b[31m[no se pudo iniciar claude]\x1b[0m\r\n")
        except Exception:
            pass
        await websocket.close()
        return

    await sess.attach(websocket)
    try:
        while True:
            msg = await websocket.receive_text()
            if msg[:1] == "{" and '"type"' in msg:
                try:
                    j = json.loads(msg)
                except Exception:
                    j = None
                if isinstance(j, dict) and j.get("type") == "resize":
                    sess.resize(int(j.get("rows") or 28), int(j.get("cols") or 100))
                    continue
                if isinstance(j, dict) and j.get("type") == "ping":
                    sess.last_activity = time.time()
                    try:
                        await websocket.send_text(json.dumps({"type": "pong", "t": int(time.time())}))
                    except Exception:
                        break
                    continue
            if not sess.write(msg.encode("utf-8")):
                break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        sess.detach(websocket)
