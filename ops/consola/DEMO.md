# Consola Claude Code embebida en BORJA — cómo funciona y cómo desplegar

Un Quant entra a BORJA por web y en el sidebar tiene **Consola** → una terminal
**Claude Code idéntica** a la CLI, embebida en el dashboard.

## Mecanismo (nativo — sin binarios externos)

Portado del proyecto Purple SHIELD (`IA_CYBER_AUDIT_ENTERPRISE/dashboard/claude_chat.py`),
adaptado a FastAPI:

```
Navegador  ──/consola──▶  página con xterm.js (frontend/templates/consola.html)
   │  WebSocket same-origin
   ▼
/ws/consola/terminal  (backend/consola.py)
   │  pty.fork()  →  os.execvpe("claude")
   ▼
proceso `claude` real en una PTY, cwd = repo (o CONSOLA_CWD)
```

- **Sin ttyd / wetty / Docker**: `pty`, `os`, `termios` son stdlib; el WebSocket es
  nativo de FastAPI; `xterm.js` se carga por CDN. **No se instala nada nuevo.**
- **Sin API key**: se hace *scrub* de `ANTHROPIC_API_KEY` → `claude` usa la sesión
  OAuth guardada del usuario del host (`~/.claude.json`). Por eso corre como "Claude Max".
- **Same-origin**: la terminal vive en `/consola` del mismo dashboard (no hay 2º puerto
  ni iframe cross-origin).
- **Auth**: la página `/consola` la protege el `AuthMiddleware` (cookie). El WebSocket
  —que el middleware NO cubre— se autentica solo con la misma cookie + check de Origin
  (anti-CSWSH) dentro del handler.

## Archivos

| Archivo | Rol |
|---|---|
| `backend/consola.py` | router: página `/consola`, `/ws/consola/terminal` (bridge PTY↔WS), `/api/consola/status`. |
| `frontend/templates/consola.html` | xterm.js + cliente WS (reconexión, resize, ping). |
| `backend/main.py` | `app.include_router(consola_router)` — **ya cableado**. |
| `frontend/templates/base.html` | link "Consola" en el sidebar — **ya cableado**. |

## Estado en localhost (este notebook)

✅ **Funcionando.** Se cableó, se validó el import, se reinició `borja.service` y se
verificó en el navegador: terminal conectada, `claude` v2.1.218 (Opus 4.7 · Claude Max)
corriendo en `/DATA/I-314/FINANCE`.

## Desplegar en la VM de GCP (IP pública:4151)

Como todo es código del repo, el clon ya trae la consola. En la VM:

1. **`claude` instalado y logueado como el usuario del servicio BORJA.** Es la única
   dependencia real (se usa su OAuth). Si aún no:
   ```bash
   npm install -g @anthropic-ai/claude-code
   claude   # una vez, para hacer login OAuth (queda en ~/.claude.json)
   ```
2. **WebSockets en uvicorn:** asegurar `websockets` instalado (viene con
   `uvicorn[standard]`; acá ya está, v16).
3. **BORJA público en 4151:** en `borja.service`, `--host 0.0.0.0 --port 4151`.
   Firewall de GCP: abrir **sólo 4151** (la consola es same-origin, no necesita 2º puerto).
4. Reiniciar BORJA. Listo: sidebar → **Consola**.

### Variables opcionales
- `CONSOLA_CWD=/ruta` — dónde arranca `claude` (default: raíz del repo). Para aislar al
  Quant, apuntá a un clone separado.
- `CONSOLA_ENABLED=0` — apaga la consola (la página muestra "deshabilitada").
- `CONSOLA_ALLOWED_ORIGINS=https://tu-dominio` — orígenes extra permitidos para el WS
  (si servís detrás de un dominio/proxy distinto al Host).
- `CLAUDE_BIN=/ruta/claude` — si `claude` no está en el PATH del servicio.

## Seguridad (demo vs. producción)

Para el **demo** en IP pública alcanza: el WS exige la cookie de sesión de BORJA + mismo
Origin, e ignora la API key. Si querés endurecer (multi-usuario real, aislamiento fuerte),
ver `README.md`: correr `claude` en un contenedor con workspace/DB aislados, RBAC por
usuario, y GCP IAP delante. Ojo con los hallazgos de `README.md §4` (`/api/*` sin auth,
cookie `secure=False`) antes de exponer en serio.

> El unit `borja-consola.service` (ttyd) quedó **obsoleto** — el enfoque nativo no usa ttyd.
